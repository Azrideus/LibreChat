import pdfplumber
from langchain_community.document_loaders import PyPDFLoader
import pymupdf4llm
from PyMuPDF4LLMLoader import PyMuPDF4LLMLoader
pdf_path = "./gebra-knowledge/docs/RM3100-User-Manual.pdf"

print(f"pymupdf4llm start")
mfile = PyMuPDF4LLMLoader(pdf_path)
print(f"pymupdf4llm load")
mfile.load()

print(f"pymupdf4llm done")
print(mfile)

print("\nAll extractions complete.")
