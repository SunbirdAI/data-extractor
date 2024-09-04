from typing import Dict, Any
from llama_index.core import Response

def process_response(response: Response) -> Dict[str, Any]:
    source_nodes = response.source_nodes
    sources = {}
    for i, node in enumerate(source_nodes, 1):
        source = format_source(node.metadata)
        if source not in sources.values():
            sources[i] = source

    markdown_text = response.response + "\n\n### Sources\n\n"
    raw_text = response.response + "\n\nSources:\n"

    for i, source in sources.items():
        markdown_text += f"{i}. {source}\n"
        raw_text += f"[{i}] {source}\n"

    return {"markdown": markdown_text, "raw": raw_text, "sources": sources}

def format_source(metadata: Dict[str, Any]) -> str:
    authors = metadata.get('authors', 'Unknown Author')
    year = metadata.get('year', 'n.d.')
    title = metadata.get('title', 'Untitled')

    author_list = authors.split(',')
    if len(author_list) > 2:
        formatted_authors = f"{author_list[0].strip()} et al."
    elif len(author_list) == 2:
        formatted_authors = f"{author_list[0].strip()} and {author_list[1].strip()}"
    else:
        formatted_authors = author_list[0].strip()

    year = 'n.d.' if year is None or year == 'None' else str(year)

    max_title_length = 250
    if len(title) > max_title_length:
        title = title[:max_title_length] + '...'

    return f"{formatted_authors} ({year}). {title}"
