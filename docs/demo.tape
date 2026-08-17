# Reproduce docs/demo.gif:
#   uv venv .testvenv && uv pip install --python .testvenv -e .
#   vhs docs/demo.tape
# docs/example-quote.json was generated with the real MockERP pricing
# path (see the `erfa audit` output below) against the RFQ lines in
# tests/fixtures/sample_rfq.txt.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 620
Set Padding 20
Set Theme "Dracula"
Set TypingSpeed 45ms

Hide
Type "source .testvenv/bin/activate"
Enter
Type "clear"
Enter
Show

Type "erfa --help"
Enter
Sleep 2000ms

Type "erfa audit docs/example-quote.json"
Enter
Sleep 3500ms
