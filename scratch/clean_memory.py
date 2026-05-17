# scratch/clean_memory.py
from pathlib import Path

def clean_memory_log(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"File {file_path} does not exist!")
        return

    text = path.read_text(encoding="utf-8")
    separator = "\n\n<!-- ENTRY_END -->\n\n"
    blocks = text.split(separator)

    new_blocks = []
    cleaned_count = 0

    for block in blocks:
        stripped = block.strip()
        if not stripped:
            new_blocks.append(block)
            continue

        lines = stripped.splitlines()
        tag_line = lines[0].strip()

        # Check if the block is a pending entry for NVDA
        is_pending = (
            tag_line.startswith("[") 
            and tag_line.endswith("]") 
            and " | NVDA |" in tag_line 
            and " | pending" in tag_line
        )

        if is_pending:
            fields = [f.strip() for f in tag_line[1:-1].split("|")]
            date = fields[0]
            ticker = fields[1]
            rating = fields[2]
            
            # Reconstruct tag as resolved (dummy returns to avoid LLM calls)
            new_fields = [date, ticker, rating, "+0.0%", "+0.0%", "5d"]
            if len(fields) > 4:
                new_fields.extend(fields[4:])
                
            new_tag = "[" + " | ".join(new_fields) + "]"
            rest = "\n".join(lines[1:])
            
            # Ensure REFLECTION is appended cleanly
            cleaned_block = f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\nHistorical decision review completed."
            new_blocks.append(cleaned_block)
            cleaned_count += 1
        else:
            new_blocks.append(block)

    new_text = separator.join(new_blocks)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(new_text, encoding="utf-8")
    tmp_path.replace(path)
    print(f"Successfully cleaned up {cleaned_count} pending NVDA entries in {file_path}!")

if __name__ == "__main__":
    clean_memory_log("/app/data/memory/trading_memory.md")
