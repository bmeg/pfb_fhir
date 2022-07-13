from pfb_fhir import initialize_model, Model


def test_model(config_paths):
    """Test config file parsing."""
    """Test model initialization."""
    for config_path in config_paths:
        model = Model.parse_file(config_path)
        assert model
        for entity_name, entity in model.entities.items():
            assert entity.id
            for link_name, link in entity.links.items():
                assert link.id


def test_initialize_model(config_paths):
    """Test model initialization."""
    for config_path in config_paths:
        model = initialize_model(config_path)
        assert model
        for entity_name, entity in model.entities.items():
            assert entity.id
            for link_name, link in entity.links.items():
                assert link.id
