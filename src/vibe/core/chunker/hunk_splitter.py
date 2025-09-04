# from typing import List
# from vibecommit.core.data.models import HunkChunk

# class HunkSplitter:
#     def __init__(self, max_changed_lines: int = 10):
#         self.max_changed_lines = max_changed_lines

#     def split_hunk(self, hunk: HunkChunk) -> List[HunkChunk]:
#         """
#         Splits a single valid HunkChunk into multiple smaller HunkChunks.
#         Adjusts @@ -a,b +c,d @@ line numbers to maintain valid patches.
#         """
#         lines = hunk.patch.splitlines()
#         # Separate file headers and hunk body
#         file_header_lines = []
#         hunk_start_idx = 0
#         for i, line in enumerate(lines):
#             if line.startswith("@@ "):
#                 hunk_start_idx = i
#                 break
#             else:
#                 file_header_lines.append(line)
#         hunk_body_lines = lines[hunk_start_idx:]

#         # Parse hunk header
#         header_line = hunk_body_lines[0]
#         import re
#         m = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", header_line)
#         if not m:
#             return [hunk]  # fallback
#         old_start = int(m.group(1))
#         old_len = int(m.group(2) or "1")
#         new_start = int(m.group(3))
#         new_len = int(m.group(4) or "1")

#         # Split by max_changed_lines
#         chunks: List[HunkChunk] = []
#         current_chunk_lines: List[str] = []
#         old_count = 0
#         new_count = 0
#         for line in hunk_body_lines[1:]:
#             current_chunk_lines.append(line)
#             if line.startswith("+") or line.startswith("-"):
#                 old_count += 1 if line.startswith("-") else 0
#                 new_count += 1 if line.startswith("+") else 0
#             # check if limit reached
#             if old_count + new_count >= self.max_changed_lines:
#                 chunk_header = f"@@ -{old_start},{old_count or 1} +{new_start},{new_count or 1} @@"
#                 patch = "\n".join(file_header_lines + [chunk_header] + current_chunk_lines)
#                 human_readable = "\n".join(l for l in current_chunk_lines if l.startswith("+") or l.startswith("-"))
#                 chunks.append(HunkChunk(header=chunk_header, patch=patch, human_readable=human_readable))

#                 # prepare for next chunk
#                 old_start += old_count
#                 new_start += new_count
#                 old_count = 0
#                 new_count = 0
#                 current_chunk_lines = []

#         if current_chunk_lines:
#             chunk_header = f"@@ -{old_start},{old_count or 1} +{new_start},{new_count or 1} @@"
#             patch = "\n".join(file_header_lines + [chunk_header] + current_chunk_lines)
#             human_readable = "\n".join(l for l in current_chunk_lines if l.startswith("+") or l.startswith("-"))
#             chunks.append(HunkChunk(header=chunk_header, patch=patch, human_readable=human_readable))

#         return chunks
