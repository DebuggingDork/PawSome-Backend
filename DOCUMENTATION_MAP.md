# 🗺️ PawSome Documentation Map

Quick reference to find the right documentation for what you need.

## 📁 Two Documentation Folders

```
PawSome/
├── docs/                    ← Setup, troubleshooting, architecture
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TROUBLESHOOTING.md
│   ├── ARCHITECTURE.md
│   ├── PORT_CONFIGURATION.md
│   ├── FIXES_APPLIED.md
│   └── RESTART_REQUIRED.txt
│
└── backend/docs/            ← API specs, endpoints, features
    ├── README.md
    ├── ENDPOINTS.md
    ├── CHAT_API.md
    ├── MATCHING_API.md
    ├── FEATURE_SUMMARY.md
    └── ...more API docs
```

## 🎯 Quick Navigation

### I need to...

| Task | Go To |
|------|-------|
| **Set up the project for the first time** | [docs/QUICK_START.md](docs/QUICK_START.md) |
| **Fix CORS or port issues** | [docs/PORT_CONFIGURATION.md](docs/PORT_CONFIGURATION.md) |
| **Troubleshoot any problem** | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| **Understand system architecture** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| **See what was fixed recently** | [docs/FIXES_APPLIED.md](docs/FIXES_APPLIED.md) |
| **Learn about API endpoints** | [backend/docs/ENDPOINTS.md](backend/docs/ENDPOINTS.md) |
| **Implement chat features** | [backend/docs/CHAT_API.md](backend/docs/CHAT_API.md) |
| **Work with matching system** | [backend/docs/MATCHING_API.md](backend/docs/MATCHING_API.md) |
| **See all features** | [backend/docs/FEATURE_SUMMARY.md](backend/docs/FEATURE_SUMMARY.md) |
| **Test the API** | [Swagger UI](http://localhost:8000/docs) (when running) |
| **Understand the full project** | [project.md](project.md) |

## 🚀 Start Here

**Brand new to PawSome?** Follow this order:

1. **[README.md](README.md)** - Project overview (5 min)
2. **[docs/QUICK_START.md](docs/QUICK_START.md)** - Get it running (10 min)
3. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Understand the design (15 min)
4. **[backend/docs/ENDPOINTS.md](backend/docs/ENDPOINTS.md)** - Learn the API (20 min)
5. **[project.md](project.md)** - Deep dive into everything (1 hour)

## 📚 Documentation Categories

### 🔧 Operations & Setup (`/docs`)
**For**: Setting up, running, and fixing the application

- **Quick Start** - First-time setup
- **Troubleshooting** - Fixing problems
- **Port Configuration** - CORS and port setup
- **Architecture** - System design overview
- **Fixes Applied** - Bug fix history

**When to use**: Setting up project, debugging issues, understanding infrastructure

### 📡 API & Features (`/backend/docs`)
**For**: Working with APIs and implementing features

- **Endpoints** - API reference
- **Chat API** - WebSocket chat
- **Matching API** - Swipe & match
- **Feature Summaries** - What's implemented
- **Testing Guides** - How to test

**When to use**: Building features, calling APIs, understanding implementation

### 📋 Project Specs (root level)
**For**: Complete project specification and planning

- **project.md** - Master specification document
- **README.md** - Quick project overview

**When to use**: Understanding scope, planning features, onboarding

## 🔍 Search by Topic

### Authentication
- Setup: [docs/QUICK_START.md](docs/QUICK_START.md#authentication)
- API: [backend/docs/ENDPOINTS.md](backend/docs/ENDPOINTS.md#authentication)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#authentication-issues)

### CORS / Ports
- Guide: [docs/PORT_CONFIGURATION.md](docs/PORT_CONFIGURATION.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#cors-errors)
- Quick Fix: [docs/QUICK_START.md](docs/QUICK_START.md#common-issues)

### Database
- Setup: [docs/QUICK_START.md](docs/QUICK_START.md#environment-variables)
- Connection Issues: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#database-connection-issues)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#database--storage)

### Chat System
- API: [backend/docs/CHAT_API.md](backend/docs/CHAT_API.md)
- Complete System: [backend/docs/CHAT_SYSTEM_COMPLETE.md](backend/docs/CHAT_SYSTEM_COMPLETE.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#real-time-architecture-websockets)

### Matching / Swiping
- API: [backend/docs/MATCHING_API.md](backend/docs/MATCHING_API.md)
- System: [backend/docs/MATCHING_SYSTEM_SUMMARY.md](backend/docs/MATCHING_SYSTEM_SUMMARY.md)
- Testing: [backend/docs/TESTING_MATCHES.md](backend/docs/TESTING_MATCHES.md)

### Photo Upload
- API: [backend/docs/ENDPOINTS.md](backend/docs/ENDPOINTS.md#photos)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#photo-upload-issues)

## 💡 Tips

### Use the Right Folder
- **Problem with setup?** → `/docs`
- **Question about API?** → `/backend/docs`
- **Need complete spec?** → `project.md`

### Start with README files
Each docs folder has a README.md:
- [docs/README.md](docs/README.md) - Operations docs index
- [backend/docs/README.md](backend/docs/README.md) - API docs index

### Use Interactive Docs
When backend is running, use Swagger UI:
- http://localhost:8000/docs - Test APIs in browser
- Much easier than reading markdown!

## 🔄 Documentation Updates

When you make changes, update docs:

**Changed API?** → Update `backend/docs/ENDPOINTS.md`  
**Fixed a bug?** → Add to `docs/TROUBLESHOOTING.md`  
**Added feature?** → Update `backend/docs/FEATURE_SUMMARY.md`  
**Setup changed?** → Update `docs/QUICK_START.md`

## 📞 Still Can't Find It?

1. Check [docs/README.md](docs/README.md) - Operations index
2. Check [backend/docs/README.md](backend/docs/README.md) - API index  
3. Search this file (Ctrl+F)
4. Check [project.md](project.md) - Everything is there!

---

**Last Updated**: July 23, 2026  
**Documentation Status**: Complete ✅
