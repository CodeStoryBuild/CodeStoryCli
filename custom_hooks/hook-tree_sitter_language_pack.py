from PyInstaller.utils.hooks import collect_all

# Collect all files from the tree_sitter_language_pack package
datas, binaries, hiddenimports = collect_all('tree_sitter_language_pack')