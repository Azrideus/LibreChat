import pdfplumber
from langchain_community.document_loaders import PyPDFLoader
import pymupdf4llm

pdf_path = "./gebra-knowledge/docs/RM3100-User-Manual.pdf"

pdfplumber_out = "./gebra-knowledge/docs/extraction_pdfplumber.txt"
pypdfloader_out = "./gebra-knowledge/docs/extraction_pypdfloader.txt"
pymupdf4llm_out = "./gebra-knowledge/docs/extraction_pymupdf4llm.txt"

# # ============================================================
# # 1. PDFPLUMBER — text + tables, page by page
# # ============================================================
# with open(pdfplumber_out, "w", encoding="utf-8") as out:
#     out.write("PDFPLUMBER EXTRACTION\n")
#     out.write("=" * 60 + "\n")

#     with pdfplumber.open(pdf_path) as pdf:
#         for page_num, page in enumerate(pdf.pages, start=1):
#             text = page.extract_text()
#             out.write(f"\n--- Page {page_num} text ---\n")
#             out.write(text if text else "[no text extracted]")
#             out.write("\n")

#             tables = page.extract_tables()
#             if not tables:
#                 out.write(f"--- Page {page_num}: no tables found ---\n")
#             for t_idx, table in enumerate(tables):
#                 out.write(f"--- Page {page_num}, Table {t_idx} ---\n")
#                 for row in table:
#                     out.write(f"{row}\n")

# print(f"pdfplumber done -> {pdfplumber_out}")

# # ============================================================
# # 2. PYPDFLOADER — text only, page by page
# # ============================================================
# with open(pypdfloader_out, "w", encoding="utf-8") as out:
#     out.write("PYPDFLOADER EXTRACTION\n")
#     out.write("=" * 60 + "\n")

#     loader = PyPDFLoader(pdf_path)
#     docs = loader.load()

#     for doc in docs:
#         page_num = doc.metadata.get("page", "?")
#         out.write(f"\n--- Page {page_num} text ---\n")
#         out.write(
#             doc.page_content if doc.page_content else "[no text extracted]")
#         out.write("\n")

# print(f"PyPDFLoader done -> {pypdfloader_out}")

# ============================================================
# 3. PYMUPDF4LLM — markdown-formatted text, page-chunked
# ============================================================
with open(pymupdf4llm_out, "w", encoding="utf-8") as out:
    out.write("PYMUPDF4LLM EXTRACTION\n")
    out.write("=" * 60 + "\n")

    # page_chunks=True returns a list of dicts, one per page,
    # each with "text" (markdown) and metadata
    md_pages = pymupdf4llm.to_markdown(
        pdf_path, page_chunks=True, ocr_language="eng+fa")

    page_index = 1
    for page_data in md_pages:
        out.write(f"\n--- Page {page_index} text (markdown) ---\n")
        out.write(page_data["text"] if page_data["text"]
                  else "[no text extracted]")
        out.write("\n")
        page_index += 1

print(f"pymupdf4llm done -> {pymupdf4llm_out}")

print("\nAll extractions complete.")
