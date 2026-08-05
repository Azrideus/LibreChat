import pymupdf4llm
from langchain_core.documents import Document


class PyMuPDF4LLMLoader:
    """Drop-in replacement for PyPDFLoader with the same `.load()`
    interface, using pymupdf4llm's markdown-aware extraction for
    better table/heading fidelity."""

    def __init__(self, file_path):
        self.file_path = file_path

    def load(self):
        md_pages = pymupdf4llm.to_markdown(
            self.file_path,
            page_chunks=True,
            table_strategy=None
        )

        docs = []
        for i, page_data in enumerate(md_pages, start=1):
            text = page_data.get("text", "")
            if not text:
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": self.file_path, "page": i},
                )
            )
        return docs
