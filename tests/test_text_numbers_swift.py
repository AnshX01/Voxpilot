from voxpilot.textnav import TextNumbering, SwiftFormatter


class FakeTarget:
    def __init__(self, text):
        self.text = text
        self.sel = None

    def get_text(self):
        return self.text

    def select_range(self, s, e):
        self.sel = (s, e)
        return True

    def get_selection(self):
        return self.sel or (0, 0)


def test_lines_numbered_then_words_then_chars():
    t = FakeTarget("hello big world\nsecond line")
    n = TextNumbering(t)
    items = n.show()
    assert [i.text for i in items] == ["hello big world", "second line"]
    assert n.select(1)
    assert t.sel == (0, 15)
    assert [i.text for i in n.items] == ["hello", "big", "world"]
    assert n.select(2)
    assert [i.text for i in n.items] == ["b", "i", "g"]


def test_apply_and_transform():
    t = FakeTarget("one two")
    n = TextNumbering(t)
    n.show(); n.select(1)
    assert n.apply("uppercase", 2) and t.sel == (4, 7)
    assert TextNumbering.transform("uppercase", "two") == "TWO"
    assert TextNumbering.transform("delete", "two") == ""
    assert TextNumbering.transform("capitalize", "two") == "Two"
    assert not n.apply("delete", 99)


def test_hide():
    n = TextNumbering(FakeTarget("a"))
    n.show(); n.hide()
    assert not n.visible and n.items == []


def test_swift_basic():
    f = SwiftFormatter()
    assert f.format("let my value equals five") == "let myValue = 5"
    assert f.format("if x double equals ten open brace") == "if x == 10 {"
    assert f.format("func add open paren a colon int comma b colon int close paren arrow int") == "func add(a: int, b: int) -> int"
