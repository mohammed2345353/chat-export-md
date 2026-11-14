import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from chat_export_md.parsers import detect, html_to_text, load, parse_chatgpt, parse_claude, parse_gemini
from chat_export_md.render import continue_prompt, slugify, to_markdown, write_all


def node(nid, parent, children, role=None, parts=None, t=None, **content):
    msg = None
    if role:
        c = {"content_type": content.pop("content_type", "text")}
        if parts is not None:
            c["parts"] = parts
        c.update(content)
        msg = {"author": {"role": role}, "content": c, "create_time": t, "metadata": {}}
    return {"id": nid, "parent": parent, "children": children, "message": msg}


CHATGPT = [{
    "id": "c1", "title": "Branched chat", "create_time": 1731000000, "update_time": 1731000500,
    "current_node": "a2b",
    "mapping": {
        "root": node("root", None, ["sys"]),
        "sys": node("sys", "root", ["u1"], "system", [""]),
        "u1": node("u1", "sys", ["a1"], "user", ["What is 2+2?"], 1731000001),
        "a1": node("a1", "u1", ["u2a", "u2b"], "assistant", ["4"], 1731000002),
        "u2a": node("u2a", "a1", ["a2a"], "user", ["old branch question"], 1731000003),
        "a2a": node("a2a", "u2a", [], "assistant", ["old branch answer"], 1731000004),
        "u2b": node("u2b", "a1", ["code"], "user", ["show code", {"content_type": "image_asset_pointer",
                                                                   "asset_pointer": "file-x"}], 1731000005),
        "code": node("code", "u2b", ["a2b"], "assistant", None, 1731000006, content_type="code",
                     language="python", text="print(4)"),
        "a2b": node("a2b", "code", [], "assistant", ["Here you go — مرحبا"], 1731000007),
    },
}]

CLAUDE = [{
    "uuid": "u-1", "name": "Plan a trip", "created_at": "2026-11-01T10:00:00Z", "updated_at": "2026-11-01T10:05:00Z",
    "chat_messages": [
        {"sender": "human", "text": "fallback text", "content": [{"type": "text", "text": "Plan 3 days in Baghdad"}],
         "created_at": "2026-11-01T10:00:00Z", "attachments": [{"file_name": "notes.txt", "extracted_content": "x"}],
         "files": []},
        {"sender": "assistant", "text": "Day 1 ...", "content": [], "created_at": "2026-11-01T10:01:00Z"},
        {"sender": "assistant", "text": "", "content": [], "created_at": "2026-11-01T10:02:00Z"},
    ],
}]

GEMINI = [
    {"header": "Gemini Apps", "title": "Prompted Write a haiku", "time": "2026-11-02T08:00:00.000Z",
     "safeHtmlItem": [{"html": "<p>Autumn leaves fall</p><ul><li>one</li><li>two</li></ul>"}]},
    {"header": "Gemini Apps", "title": "Prompted Another one", "time": "2026-11-02T09:00:00.000Z",
     "safeHtmlItem": [{"html": "<p>Ok</p>"}]},
    {"header": "Gemini Apps", "title": "Used an Extension", "time": "2026-11-02T09:05:00.000Z"},
    {"header": "Search", "title": "Prompted not gemini", "time": "2026-11-02T09:05:00.000Z"},
]


class ParserTests(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(detect(CHATGPT), "chatgpt")
        self.assertEqual(detect(CLAUDE), "claude")
        self.assertEqual(detect(GEMINI), "gemini")
        self.assertIsNone(detect({"x": 1}))

    def test_chatgpt_active_branch(self):
        c = parse_chatgpt(CHATGPT)[0]
        texts = [m.text for m in c.messages]
        self.assertEqual(texts[0], "What is 2+2?")
        self.assertNotIn("old branch answer", texts)
        self.assertEqual(texts[2], "show code\n[image]")
        self.assertEqual(texts[3], "```python\nprint(4)\n```")
        self.assertEqual(c.messages[-1].role, "assistant")
        self.assertEqual(len(c.messages), 5)

    def test_claude(self):
        c = parse_claude(CLAUDE)[0]
        self.assertEqual(len(c.messages), 2)
        self.assertEqual(c.messages[0].text, "Plan 3 days in Baghdad\n\n📎 notes.txt")
        self.assertEqual(c.messages[1].text, "Day 1 ...")

    def test_gemini(self):
        convs = parse_gemini(GEMINI)
        self.assertEqual(len(convs), 1)
        c = convs[0]
        self.assertEqual([m.role for m in c.messages], ["user", "assistant", "user", "assistant"])
        self.assertEqual(c.messages[1].text, "Autumn leaves fall\n- one\n- two")
        self.assertTrue(c.title.startswith("Gemini 2026-11-02"))
        self.assertEqual(html_to_text("<p>a &amp; b</p>"), "a & b")


class RenderTests(unittest.TestCase):
    def test_markdown_and_continue(self):
        c = parse_chatgpt(CHATGPT)[0]
        md = to_markdown(c)
        self.assertTrue(md.startswith('---\ntitle: "Branched chat"\nsource: chatgpt'))
        self.assertIn("### 🧑 You", md)
        self.assertIn("مرحبا", md)
        prompt = continue_prompt(c, 12)
        self.assertIn("earlier messages omitted", prompt)
        self.assertIn("Here you go", prompt)

    def test_slug(self):
        self.assertEqual(slugify("Plan a trip!"), "plan-a-trip")
        self.assertEqual(slugify("خطة سفر"), "خطة-سفر")
        self.assertEqual(slugify("???"), "untitled")

    def test_write_all_collisions_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            twice = CLAUDE + [dict(CLAUDE[0], uuid="u-2")]
            zpath = tmp / "export.zip"
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("conversations.json", json.dumps(twice))
            convs = load(zpath)
            self.assertEqual(len(convs), 2)
            stats = write_all(convs, tmp / "out", max_tokens=50)
            names = sorted(p.name for p in (tmp / "out").glob("*.md"))
            self.assertIn("2026-11-01-claude-plan-a-trip.md", names)
            self.assertIn("2026-11-01-claude-plan-a-trip-2.md", names)
            self.assertIn("2026-11-01-claude-plan-a-trip.continue.md", names)
            self.assertIn("index.md", names)
            self.assertEqual(stats["conversations"], 2)
            write_all(convs, tmp / "j", fmt="jsonl")
            lines = (tmp / "j" / "conversations.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["source"], "claude")

    def test_cli_folder_and_filters(self):
        from chat_export_md import cli
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "gpt").mkdir()
            (tmp / "gpt" / "conversations.json").write_text(json.dumps(CHATGPT), encoding="utf-8")
            gdir = tmp / "Takeout" / "My Activity" / "Gemini Apps"
            gdir.mkdir(parents=True)
            (gdir / "MyActivity.json").write_text(json.dumps(GEMINI), encoding="utf-8")
            out = tmp / "out"
            self.assertEqual(cli.main([str(tmp / "gpt"), str(tmp / "Takeout"), "-o", str(out),
                                       "--search", "haiku"]), 0)
            files = [p.name for p in out.glob("*.md") if p.name != "index.md"]
            self.assertEqual(len(files), 1)
            self.assertIn("gemini", files[0])
            self.assertEqual(cli.main([str(tmp / "gpt"), "--stats"]), 0)
            self.assertEqual(cli.main([str(tmp / "nothing.json")]), 1)


if __name__ == "__main__":
    unittest.main()
