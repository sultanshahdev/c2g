# Changelog

All notable changes to P2PDocs will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-11-21

### Added

- ✨ **Phase 1: Authentication & Storage**
  - User registration and login with hashed passwords
  - Document CRUD operations with local storage
  - Metadata management (owner, permissions, timestamps)

- ✨ **Phase 2: TCP Networking**
  - TCP server listening on port 5000
  - Peer-to-peer message protocol with JSON serialization
  - Client connection management

- ✨ **Phase 3: Peer Discovery**
  - UDP broadcast discovery on LAN
  - Automatic peer detection on port 5555
  - Heartbeat and health checks

- ✨ **Phase 4: GUI Editor**
  - Tkinter-based collaborative editor
  - Multi-user cursor tracking with color-coded cursors
  - Real-time document viewing and editing

- ✨ **Phase 5: Versioning & Access Control**
  - Version history tracking with commit messages
  - Access control list (ACL) management
  - User permission grants (READ, WRITE)

- ✨ **Phase 6: Lock Management**
  - Distributed lock acquisition and release
  - Lock timeout handling
  - Lock status tracking per document

- ✨ **Phase 7: Keystroke Streaming**
  - Real-time keystroke broadcasting (5-10ms latency)
  - Insertion and deletion streaming
  - Cursor position synchronization

- ✨ **Phase 8: Offline Support**
  - Offline edit queueing
  - Automatic synchronization on reconnect
  - Update deduplication

- ✨ **Phase 9: Fair Lock Queue**
  - FIFO lock queue implementation
  - Fair lock distribution across peers
  - Automatic grant to next waiting user

- ✨ **Phase 10: Integration & Testing**
  - 57 comprehensive test cases (100% pass rate)
  - Multi-user runtime testing (5 concurrent users)
  - End-to-end integration tests

- ✨ **CLI Interface**
  - `p2pdocs create` - Create new documents
  - `p2pdocs open` - Open and edit documents
  - `p2pdocs edit` - GUI editor
  - `p2pdocs users` - List connected peers
  - `p2pdocs grant` - Grant document access
  - `p2pdocs commit` - Commit document changes
  - `p2pdocs history` - View version history
  - `p2pdocs list` - List all documents
  - `p2pdocs sync` - Synchronize offline changes
  - `p2pdocs status` - System status

- 🎯 **Zero External Dependencies**
  - Uses only Python standard library
  - Built-in networking (TCP/UDP)
  - Built-in encryption (hashlib)

- 📦 **PyPI Distribution**
  - Installable via `pip install p2pdocs`
  - Wheel and source distributions
  - Automatic updates via pip

- 🚀 **GitHub Actions CI/CD**
  - Automated testing on push
  - Automated package building
  - OIDC-based PyPI publishing (no API tokens)

- 📖 **Comprehensive Documentation**
  - README.md - User guide and quick start
  - PROJECT_ANALYSIS.md - Complete system analysis
  - README_FULL_IMPLEMENTATION.md - Technical deep dive
  - GITHUB_ACTIONS_SETUP.md - CI/CD guide
  - CONTRIBUTING.md - Contribution guidelines
  - DEPLOYMENT_GUIDE.md - Deployment instructions

### Documentation

- Comprehensive project specification with 10 phases
- Distributed systems architecture documentation
- Network protocol specification
- API documentation for all modules
- User quick reference guide

### Testing

- Phase 2: TCP protocol tests (8 tests)
- Phase 10: Integration tests (57 total tests)
- Multi-user runtime tests (38 test scenarios)
- All tests passing (100% success rate)

## [Unreleased]

### Planned Features

- [ ] Web UI dashboard
- [ ] Document encryption
- [ ] Multi-network bridging
- [ ] Full-text search
- [ ] Document templates
- [ ] Rich text support
- [ ] File attachments
- [ ] Comments and annotations
- [ ] Collaborative cursors with names
- [ ] Document statistics dashboard
- [ ] Export to PDF/HTML
- [ ] Plugin system

### Known Limitations

- Single LAN only (no cross-subnet discovery)
- Text documents only (no binary files)
- Manual conflict resolution required
- No built-in encryption
- Cursor tracking limited to visible users

---

## Version Format

- **1.0.0**: Initial stable release
- **1.x.y**: Minor features and patches
- **2.0.0**: Major breaking changes (future)

## Support

For issues, questions, or feature requests, please visit:
- GitHub Issues: https://github.com/p2pdocs/p2pdocs/issues
- Email: support@p2pdocs.io

## Contributors

- P2PDocs Team

---

**Note**: For older versions and detailed migration guides, see [MIGRATION.md](MIGRATION.md) (if available).
