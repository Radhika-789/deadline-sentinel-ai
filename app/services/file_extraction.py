"""
Utilities for extracting plain text from uploaded files.

This service is intentionally independent from FastAPI, SQLAlchemy,
and Gemini. Its only responsibility is converting uploaded files into
plain text.

Supported formats:
- PDF
- DOCX
- TXT
- PNG
- JPG
- JPEG
"""

from io import BytesIO
import xml.etree.ElementTree as ET
import zipfile

import pdfplumber


class FileExtractionError(Exception):
    """Raised when text extraction from a file fails."""


class FileExtractionService:
    """
    Extract text from uploaded files.

    This service performs no direct database operations.
    It converts supported files into raw text that can later
    be passed to GeminiExtractionService.
    """

    def extract_pdf(self, file_bytes: bytes) -> str:
        """
        Extract text from a PDF.

        Parameters
        ----------
        file_bytes : bytes
            Raw uploaded PDF bytes.

        Returns
        -------
        str
            Extracted plain text.

        Raises
        ------
        FileExtractionError
            If the PDF cannot be parsed or contains no text.
        """
        try:
            extracted_pages = []
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_pages.append(text)

            full_text = "\n\n".join(extracted_pages).strip()
            if not full_text:
                raise FileExtractionError(
                    "The uploaded PDF does not contain extractable text."
                )
            return full_text

        except FileExtractionError:
            raise
        except Exception as exc:
            raise FileExtractionError(
                f"Failed to read PDF: {exc}"
            ) from exc

    def extract_docx(self, file_bytes: bytes) -> str:
        """
        Extract text from a DOCX file by parsing word/document.xml inside the zip.

        Parameters
        ----------
        file_bytes : bytes
            Raw uploaded DOCX bytes.

        Returns
        -------
        str
            Extracted plain text.

        Raises
        ------
        FileExtractionError
            If the DOCX cannot be parsed or contains no text.
        """
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as docx:
                xml_content = docx.read("word/document.xml")
                root = ET.fromstring(xml_content)
                
                # Extract text elements under paragraph tags
                # WordprocessingML namespace
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                p_tag = f"{ns}p"
                t_tag = f"{ns}t"
                
                paragraphs = []
                for p in root.iter(p_tag):
                    texts = [t.text for t in p.iter(t_tag) if t.text]
                    if texts:
                        paragraphs.append("".join(texts))
                
                full_text = "\n".join(paragraphs).strip()
                if not full_text:
                    raise FileExtractionError(
                        "The uploaded DOCX does not contain extractable text."
                    )
                return full_text
        except FileExtractionError:
            raise
        except Exception as exc:
            raise FileExtractionError(
                f"Failed to read DOCX: {exc}"
            ) from exc

    def extract_txt(self, file_bytes: bytes) -> str:
        """
        Extract text from a raw text file (TXT).

        Parameters
        ----------
        file_bytes : bytes
            Raw uploaded TXT bytes.

        Returns
        -------
        str
            Extracted plain text.

        Raises
        ------
        FileExtractionError
            If the TXT cannot be decoded.
        """
        try:
            # Try decoding with UTF-8 first, fallback to Latin-1
            try:
                full_text = file_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                full_text = file_bytes.decode("latin-1").strip()
            
            if not full_text:
                raise FileExtractionError(
                    "The uploaded TXT file is empty."
                )
            return full_text
        except FileExtractionError:
            raise
        except Exception as exc:
            raise FileExtractionError(
                f"Failed to read TXT: {exc}"
            ) from exc

    def extract_image(self, file_bytes: bytes, api_key: str | None = None) -> str:
        """
        Extract text from an image using Gemini's multimodal capabilities (OCR).

        Parameters
        ----------
        file_bytes : bytes
            Raw uploaded image bytes.
        api_key : str | None
            Optional Gemini API key. If not provided, it will be loaded from settings.

        Returns
        -------
        str
            Extracted plain text.

        Raises
        ------
        FileExtractionError
            If OCR fails.
        """
        from PIL import Image
        import google.generativeai as genai
        from app.core.config import settings

        try:
            genai.configure(api_key=api_key or settings.gemini_api_key)
            model = genai.GenerativeModel("gemini-flash-latest")
            
            image = Image.open(BytesIO(file_bytes))
            prompt = (
                "Perform OCR on this image. Extract all text from this image exactly, "
                "preserving the layout, line breaks, and structure as much as possible. "
                "Do not add any explanations, markdown code blocks, or preamble. "
                "Return ONLY the extracted text."
            )
            response = model.generate_content([image, prompt])
            
            text = getattr(response, "text", None)
            if not text or not text.strip():
                raise FileExtractionError("No text could be extracted from the image.")
                
            return text.strip()
            
        except FileExtractionError:
            raise
        except Exception as exc:
            raise FileExtractionError(f"Failed to perform Image OCR: {exc}") from exc