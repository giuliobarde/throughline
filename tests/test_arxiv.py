from pipeline.sources.arxiv import parse_arxiv_feed

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Scaling Laws for Widgets</title>
    <summary>We study widgets. Code available.</summary>
    <published>2026-06-05T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate"/>
  </entry>
</feed>"""


def test_parse_arxiv_feed_extracts_items():
    items = parse_arxiv_feed(SAMPLE)
    assert len(items) == 1
    it = items[0]
    assert it.id == "2401.00001"
    assert it.source == "arxiv"
    assert it.title == "Scaling Laws for Widgets"
    assert it.authors == ["Ada Lovelace", "Alan Turing"]
    assert it.url == "http://arxiv.org/abs/2401.00001v1"
    assert it.has_code is True  # "code" mentioned in summary
