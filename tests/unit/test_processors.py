"""Unit tests for the built-in processors."""

from app.processors import metadata, sha256, word_count


async def test_word_count_counts_whitespace_separated_words() -> None:
    result = await word_count.process(b"the quick brown fox")

    assert result == {"word_count": 4}


async def test_word_count_handles_empty_input() -> None:
    result = await word_count.process(b"")

    assert result == {"word_count": 0}


async def test_sha256_matches_known_digest() -> None:
    result = await sha256.process(b"hello")

    assert result == {
        "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    }


async def test_metadata_reports_size_in_bytes() -> None:
    result = await metadata.process(b"12345")

    assert result == {"size_bytes": 5}
