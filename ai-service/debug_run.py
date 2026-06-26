from ingest import find_markdown_files, load_documents, split_documents, DOCS_DIR

files = find_markdown_files(DOCS_DIR)
print('found files', len(files))
docs = load_documents(files)
print('loaded docs', len(docs))
if docs:
    print('first doc source:', docs[0]['metadata'].get('source'))
    print('first doc len', len(docs[0]['page_content']))
chunks = split_documents(docs)
print('chunks', len(chunks))
if chunks:
    print('first chunk preview:', chunks[0]['page_content'][:200])
