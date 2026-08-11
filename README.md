# narou2kindle

A small CLI that converts public novels from Shosetsuka ni Naro, Nocturne Novels, and Hameln into EPUB 3 files. EPUB files can be read in Calibre or sent to Kindle using Amazon's Send to Kindle service.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Usage

```powershell
python .\run.py https://ncode.syosetu.com/n4298mo/
```

By default, the EPUB is created in the current directory using the novel title as its filename. Use `-o` / `--output` to set the full output file path. The `.epub` extension is added automatically when omitted.

```powershell
python .\run.py https://ncode.syosetu.com/n4298mo/ --output .\books\my-novel
```

Prose is reflowed into paragraphs of up to 220 characters. A sparse blank line is inserted at the next eligible boundary after 1,000 characters; a run of dialogue is never split. Change or disable this behavior as needed:

```powershell
python .\run.py https://ncode.syosetu.com/n4298mo/ --paragraph-length 220 --section-length 1000
python .\run.py https://ncode.syosetu.com/n4298mo/ --section-length 0
```

The first readable page is a linked table of contents. To include a cover, pass an image file (JPG, PNG, GIF, or WebP). WebP covers are automatically converted to JPEG inside the EPUB for Kindle compatibility:

```powershell
python .\run.py https://ncode.syosetu.com/n4298mo/ --cover .\cover.jpg
```

Vertical, right-to-left reading is the default. Use horizontal, left-to-right reading when needed:

```powershell
python .\run.py https://ncode.syosetu.com/n4298mo/ --writing-mode horizontal
```

The tool is intended for converting public works for personal reading. It does not include downloaded novels, cover images, browser cookies, or account credentials.

## License

MIT. See [LICENSE](LICENSE).
