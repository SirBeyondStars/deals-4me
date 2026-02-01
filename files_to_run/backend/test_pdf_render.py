import fitz  # PyMuPDF

pdf_path = r"C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers\shaws\week51\raw_pdf\shaws.pdf"  # <-- confirm this is the real location
doc = fitz.open(pdf_path)

page = doc.load_page(0)
pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), alpha=False)
pix.save("test_page_01.png")

print("Saved test_page_01.png")
