"""
Document Service — Handles document upload, extraction, classification, and AI creation.
"""
import os
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.document import Document, DocumentReference
from app.dtap import DTAPRegistry

logger = logging.getLogger(__name__)


class DocumentService:
    """Service layer for document operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        company_id: str,
        user_id: str,
        metadata: dict,
    ) -> Document:
        """
        Process an uploaded document:
        1. Save file to storage
        2. Extract text content
        3. Classify document type
        4. Assign DTAP
        5. Store in database
        """
        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

        # Extract text from bytes in memory (before any storage write)
        extracted_text = await self._extract_text_from_bytes(file_content, file_type)
        extracted_sections = self._identify_sections(extracted_text)

        # Save file to storage (Supabase in prod, local in dev)
        file_path = self._save_file(file_content, filename, company_id)

        # Auto-classify if metadata not provided
        document_category = metadata.get("document_category", "")
        if not document_category:
            document_category = self._auto_classify(filename, extracted_text)

        # Resolve DTAP
        dtap = DTAPRegistry.get_by_category(document_category)
        dtap_id = dtap.dtap_id if dtap else None

        # Create record
        document = Document(
            company_id=company_id,
            uploaded_by=user_id,
            title=metadata.get("title", filename),
            document_number=metadata.get("document_number"),
            version=metadata.get("version", "1.0"),
            function_type=metadata.get("function_type"),
            regulatory_category=metadata.get("regulatory_category"),
            department_owner=metadata.get("department_owner"),
            document_category=document_category,
            regulatory_frameworks=metadata.get("regulatory_frameworks"),
            dtap_id=dtap_id,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=len(file_content),
            extracted_text=extracted_text,
            extracted_sections=extracted_sections,
            status="ready",
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def add_reference(
        self,
        document_id: str,
        file_content: bytes,
        filename: str,
        user_id: str,
        title: str,
        description: str = "",
        reference_type: str = "organizational_guideline",
    ) -> DocumentReference:
        """
        Add a user-uploaded reference to a document.
        These references are used during assessment as organizational context.
        """
        # Get the parent document for company context
        doc = await self.db.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

        # Extract text from bytes in memory
        extracted_text = await self._extract_text_from_bytes(file_content, file_type)

        # Save file to storage (Supabase in prod, local in dev)
        file_path = self._save_file(file_content, filename, doc.company_id, subfolder="references")

        reference = DocumentReference(
            document_id=document_id,
            uploaded_by=user_id,
            title=title or filename,
            description=description,
            file_path=file_path,
            file_type=file_type,
            extracted_text=extracted_text,
            reference_type=reference_type,
        )

        self.db.add(reference)
        await self.db.commit()
        await self.db.refresh(reference)
        return reference

    async def get_document_with_references(self, document_id: str) -> dict:
        """Get document and its references for assessment"""
        doc = await self.db.get(Document, document_id)
        if not doc:
            return None

        # Load references
        result = await self.db.execute(
            select(DocumentReference).where(DocumentReference.document_id == document_id)
        )
        references = result.scalars().all()

        return {
            "document": doc,
            "references": [
                {
                    "id": ref.id,
                    "title": ref.title,
                    "extracted_text": ref.extracted_text,
                    "reference_type": ref.reference_type,
                }
                for ref in references
            ],
        }

    def _save_file(self, content: bytes, filename: str, company_id: str, subfolder: str = "documents") -> str:
        """Upload to Supabase Storage in production, local filesystem in development."""
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            from supabase import create_client
            storage_path = f"{company_id}/{subfolder}/{filename}"
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                storage_path, content, {"upsert": "true"}
            )
            return storage_path
        storage_dir = os.path.join(settings.STORAGE_PATH, company_id, subfolder)
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    async def _extract_text_from_bytes(self, content: bytes, file_type: str) -> str:
        """Extract text from document bytes in memory (no disk I/O)."""
        import io
        if file_type == "docx":
            try:
                from docx import Document as DocxDocument
                doc = DocxDocument(io.BytesIO(content))
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as e:
                logger.error(f"DOCX extraction failed: {e}")
                return ""
        elif file_type == "pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                return ""
        elif file_type in ("txt", "md"):
            return content.decode("utf-8", errors="ignore")
        return ""

    def _identify_sections(self, text: str) -> dict:
        """Identify document sections from extracted text"""
        sections = {}
        current_section = "preamble"
        current_content = []

        for line in text.split("\n"):
            stripped = line.strip()
            # Heuristic: lines that are short, capitalized/numbered are likely headers
            if (
                stripped
                and len(stripped) < 100
                and (stripped.isupper() or stripped[0].isdigit() or stripped.endswith(":"))
            ):
                if current_content:
                    sections[current_section] = "\n".join(current_content)
                current_section = stripped
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def _auto_classify(self, filename: str, text: str) -> str:
        """Auto-classify document category from filename and content"""
        filename_lower = filename.lower()
        text_lower = text[:2000].lower()

        if "sop" in filename_lower or "standard operating" in text_lower:
            return "SOP"
        elif "capa" in filename_lower or "corrective and preventive" in text_lower:
            return "CAPA"
        elif "atm" in filename_lower or "analytical test method" in text_lower or "test method" in text_lower:
            return "ATM"
        elif "deviation" in filename_lower or "deviation report" in text_lower:
            return "Deviation"
        elif "validation" in filename_lower:
            return "Validation"
        else:
            return "Other"
