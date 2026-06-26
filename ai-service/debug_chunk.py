from ingest import find_markdown_files, load_documents, _chunk_text, DOCS_DIR

files = find_markdown_files(DOCS_DIR)
docs = load_documents(files)
text = docs[0]['page_content']
print('text len', len(text))
parts = __import__('re').split(r'(?m)(?=^#{1,6}\s)', text)
print('parts count regex:', len(parts))
parts2 = text.split('\n\n')
print('parts2 count double newline:', len(parts2))
chunks = _chunk_text(text)
print('chunks count', len(chunks))
if chunks:
    print('first chunk len', len(chunks[0]))
    print(chunks[0][:200])
