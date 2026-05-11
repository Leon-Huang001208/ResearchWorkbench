"""Unit tests for entity resolution module."""
from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer
from knowledge_layer.entity_resolution.resolver import EntityResolver
from knowledge_layer.entity_resolution.types import EntityType


def test_canonicalizer_generate_id():
    """Test canonicalizer ID generation."""
    canonicalizer = Canonicalizer()
    canonical_id = canonicalizer.generate_id("贵州茅台", EntityType.COMPANY)
    assert canonical_id is not None
    assert "equity" in canonical_id
    assert "贵州茅台" in canonical_id


def test_entity_resolver_extract_stock_codes():
    """Test extracting stock codes from text."""
    resolver = EntityResolver()
    text = "关注 600519.SH 和 000001.SZ 的走势"
    candidates = resolver.extract_candidates(text)
    assert len(candidates) >= 2
    stock_codes = [c.text for c in candidates]
    assert "600519" in stock_codes
    assert "000001" in stock_codes


def test_entity_resolver_extract_by_dictionary():
    """Test extracting entities by dictionary."""
    resolver = EntityResolver()
    text = "贵州茅台和腾讯控股是好公司"
    candidates = resolver.extract_candidates(text)
    texts = [c.text for c in candidates]
    assert "贵州茅台" in texts
    assert "腾讯控股" in texts


def test_entity_resolver_resolve_direct():
    """Test resolving entities directly."""
    resolver = EntityResolver()
    resolved = resolver.resolve("人工智能")
    assert resolved is not None
    assert resolved.entity_type == EntityType.CONCEPT
    assert resolved.canonical_name == "人工智能"


def test_entity_resolver_resolve_with_candidate():
    """Test resolving entities with candidates."""
    resolver = EntityResolver()
    resolved = resolver.resolve("600519.SH")
    assert resolved is not None
    assert resolved.entity_type == EntityType.COMPANY
    assert "600519" in resolved.canonical_name or "600519" in resolved.matched_text


def test_entity_resolver_deduplicate_candidates():
    """Test deduplicating entity candidates."""
    resolver = EntityResolver()
    text = "贵州茅台贵州茅台"
    candidates = resolver.extract_candidates(text)
    # Should be deduplicated
    company_count = sum(1 for c in candidates if c.text == "贵州茅台")
    assert company_count == 1


def test_entity_resolver_extract_concepts():
    """Test extracting concept entities."""
    resolver = EntityResolver()
    text = "关注人工智能和新能源的发展"
    candidates = resolver.extract_candidates(text)
    types = [c.entity_type for c in candidates]
    assert EntityType.CONCEPT in types
    concepts = [c.text for c in candidates if c.entity_type == EntityType.CONCEPT]
    assert "人工智能" in concepts or "新能源" in concepts
