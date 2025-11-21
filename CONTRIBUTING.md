# Contributing to P2PDocs

Thank you for your interest in contributing to P2PDocs! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### 1. Report Bugs

If you find a bug, please open an issue with:

- **Title**: Brief description of the bug
- **Environment**: Python version, OS, network setup
- **Steps to Reproduce**: Detailed reproduction steps
- **Expected vs Actual**: What should happen vs what happens
- **Logs/Screenshots**: Any error messages or relevant output

### 2. Suggest Features

Feature requests are welcome! Please open an issue with:

- **Title**: Feature summary
- **Description**: Detailed explanation of the feature
- **Use Case**: Why this feature is needed
- **Proposed Solution**: If you have ideas
- **Alternatives**: Other possible approaches

### 3. Submit Pull Requests

#### Before You Start

1. **Fork the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/p2pdocs.git
   cd p2pdocs
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or for bugfixes:
   git checkout -b bugfix/your-bug-name
   ```

3. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

#### Making Changes

1. **Code Style**
   - Follow PEP 8 conventions
   - Use `black` for formatting: `black p2pdocs/`
   - Use `flake8` for linting: `flake8 p2pdocs/`
   - Maximum line length: 100 characters

2. **Type Hints**
   - Add type hints to new functions
   - Use `mypy` for checking: `mypy p2pdocs/`

3. **Testing**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test file
   pytest tests/test_phase2_protocol.py
   
   # Run with coverage
   pytest --cov=p2pdocs tests/
   ```

4. **Documentation**
   - Update docstrings for new/modified functions
   - Update README.md if adding features
   - Add comments for complex logic

#### Commit Messages

Follow conventional commits:

```
type(scope): description

body (optional)

footer (optional)
```

**Types**: feat, fix, docs, style, refactor, test, chore

**Examples**:
```
feat(network): add UDP broadcast discovery
fix(locking): handle concurrent lock requests correctly
docs(readme): add installation instructions
```

#### Submitting the PR

1. **Push your branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Clear description of changes
   - Reference related issues
   - Link to any documentation
   - Screenshots if UI changes

3. **PR Checklist**
   - [ ] Code follows PEP 8 style
   - [ ] Tests pass locally
   - [ ] New tests added for new features
   - [ ] Documentation updated
   - [ ] Commit messages are clear
   - [ ] No unrelated changes included

## Development Workflow

### Project Structure

```
p2pdocs/
├── p2pdocs/              # Main package
│   ├── auth.py           # Authentication
│   ├── cli.py            # CLI interface
│   ├── gui.py            # GUI editor
│   ├── storage.py        # Document storage
│   ├── versioning.py     # Version control
│   ├── locking.py        # Lock management
│   ├── sync.py           # Offline sync
│   ├── streaming.py      # Keystroke streaming
│   ├── queue.py          # Lock queue
│   └── network/          # Network modules
│       ├── protocol.py   # TCP protocol
│       ├── server.py     # TCP server
│       ├── client.py     # TCP client
│       └── discovery.py  # Peer discovery
├── tests/                # Test files
├── setup.py              # Setup configuration
└── pyproject.toml        # Project metadata
```

### Testing Guidelines

1. **Unit Tests**: Test individual modules in isolation
2. **Integration Tests**: Test component interactions
3. **E2E Tests**: Test complete workflows

Example test structure:
```python
def test_feature_description():
    """Test that feature works correctly."""
    # Arrange
    setup_test_data()
    
    # Act
    result = perform_action()
    
    # Assert
    assert result == expected_value
```

## Code Review Process

All pull requests require:

1. **Code review** - at least one approval
2. **Tests passing** - GitHub Actions must pass
3. **Documentation** - updated if needed
4. **No conflicts** - with main branch

## Reporting Security Issues

**Do not open public issues for security vulnerabilities!**

Please email security issues to `support@p2pdocs.io` with:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Recognition

Contributors will be recognized in:
- CHANGELOG.md
- GitHub Contributors page
- Release notes

## Questions?

- Check [FAQ](README.md#faq)
- Open a discussion on GitHub
- Email support@p2pdocs.io

---

**Thank you for contributing to P2PDocs!** 🎉

Your efforts help make peer-to-peer collaboration better for everyone.
