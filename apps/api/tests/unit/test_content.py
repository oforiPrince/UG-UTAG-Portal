from utag_api.services.content import sanitize_html


def test_sanitize_html_removes_active_content_and_secures_links() -> None:
    cleaned = sanitize_html(
        "<p>Hello<script>alert(1)</script>"
        '<a href="https://example.org" rel="opener" onclick="bad()">Read</a></p>'
    )

    assert "script" not in cleaned
    assert "onclick" not in cleaned
    assert 'rel="noopener noreferrer"' in cleaned
    assert 'href="https://example.org"' in cleaned


def test_sanitize_html_preserves_safe_editor_formatting() -> None:
    cleaned = sanitize_html(
        "<h2>Update</h2><p><strong>Bold</strong>, <u>underlined</u>, "
        "<s>revised</s>, and <code>coded</code>.</p>"
        "<blockquote><p>Quoted</p></blockquote><hr>"
        "<ul><li>First</li></ul>"
    )

    assert "<h2>Update</h2>" in cleaned
    assert "<strong>Bold</strong>" in cleaned
    assert "<u>underlined</u>" in cleaned
    assert "<s>revised</s>" in cleaned
    assert "<code>coded</code>" in cleaned
    assert "<blockquote>" in cleaned
    assert "<hr>" in cleaned
    assert "<ul><li>First</li></ul>" in cleaned
