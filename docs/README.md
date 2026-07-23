# 📚 PawSome Documentation

Welcome to the PawSome documentation! This folder contains **setup guides, troubleshooting, and system architecture**.

## 📖 Documentation Structure

PawSome has **two documentation folders**:

| Folder | Purpose | For Whom |
|--------|---------|----------|
| **`/docs`** (this folder) | Setup, troubleshooting, architecture | Developers setting up the project |
| **`/backend/docs`** | API specs, endpoint docs, feature guides | Developers using/extending the API |

### This Folder (`/docs`) - Setup & Operations
Contains guides for **getting started, fixing problems, and understanding the system**:
- Setup instructions
- Troubleshooting guides
- System architecture
- Port configuration
- Bug fix history

### Backend Folder (`/backend/docs`) - API Documentation
Contains **API-specific documentation**:
- Endpoint specifications
- Request/response examples
- Feature implementation guides
- API testing docs

## 🚀 Getting Started

**New to PawSome?** Start here:
1. **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
2. **[RESTART_REQUIRED.txt](RESTART_REQUIRED.txt)** - Important: Read this if you just updated!

## 📖 Documentation Index

### Setup & Operations
| Document | Description | When to Read |
|----------|-------------|--------------|
| **[Quick Start Guide](QUICK_START.md)** | Setup instructions, environment variables, first run | Setting up for the first time |
| **[Port Configuration](PORT_CONFIGURATION.md)** | Port setup, CORS configuration reference | Getting CORS errors |
| **[RESTART_REQUIRED.txt](RESTART_REQUIRED.txt)** | Post-update restart instructions | After pulling latest changes |

### Technical Reference
| Document | Description | When to Read |
|----------|-------------|--------------|
| **[Architecture Overview](ARCHITECTURE.md)** | System design, data flows, tech stack | Understanding how things work |
| **[Troubleshooting Guide](TROUBLESHOOTING.md)** | Solutions for common problems | When something breaks |
| **[Fixes Applied](FIXES_APPLIED.md)** | History of bug fixes and solutions | Understanding what changed |

## 🔍 Quick Links by Problem

### "Backend not running" error
→ Read: [Quick Start Guide - How to Start](QUICK_START.md#-solution-start-both-services)

### CORS / Port mismatch errors
→ Read: [Port Configuration](PORT_CONFIGURATION.md)

### Database connection timeout
→ Read: [Troubleshooting Guide - Database Issues](TROUBLESHOOTING.md#database-connection-issues)

### Photo upload not working
→ Read: [Troubleshooting Guide - Photo Upload](TROUBLESHOOTING.md#photo-upload-issues)

### Authentication failures
→ Read: [Troubleshooting Guide - Auth Issues](TROUBLESHOOTING.md#authentication-issues)

### Want to understand the system
→ Read: [Architecture Overview](ARCHITECTURE.md)

## 📋 Recommended Reading Order

### For First-Time Setup
1. [Quick Start Guide](QUICK_START.md) - Get everything running
2. [Port Configuration](PORT_CONFIGURATION.md) - Understand port setup
3. [Architecture Overview](ARCHITECTURE.md) - Learn the system

### For Troubleshooting
1. [Troubleshooting Guide](TROUBLESHOOTING.md) - Find your specific issue
2. [Port Configuration](PORT_CONFIGURATION.md) - If CORS-related
3. [Fixes Applied](FIXES_APPLIED.md) - See what was already fixed

### For Development
1. [Architecture Overview](ARCHITECTURE.md) - Understand the design
2. [Quick Start Guide](QUICK_START.md) - Reference for commands
3. [Troubleshooting Guide](TROUBLESHOOTING.md) - Debug issues

## 🔗 Backend API Documentation

For **API endpoint specs and feature guides**, see:
- **[Backend Docs Index](../backend/docs/)** - All backend documentation
- **[API Endpoints](../backend/docs/ENDPOINTS.md)** - Complete endpoint reference
- **[Chat API](../backend/docs/CHAT_API.md)** - Real-time chat system
- **[Matching API](../backend/docs/MATCHING_API.md)** - Swipe & match system
- **[Swagger UI](http://localhost:8000/docs)** - Interactive API docs (when running)

## 🎯 Common Commands

```bash
# Start both services
START_BOTH.bat

# Test connection
TEST_CONNECTION.bat

# Test database
cd backend
uv run python test_db_connection.py

# Push backend changes
cd backend
push-backend.bat

# Push frontend changes
cd frontend
push-frontend.bat
```

## 📞 Need More Help?

1. Check the [Troubleshooting Guide](TROUBLESHOOTING.md) first
2. Look at backend terminal logs for errors
3. Check browser console (F12) for frontend errors
4. Run diagnostics: `TEST_CONNECTION.bat`
5. Test database: `backend/test_db_connection.py`

## 🔄 Keep Documentation Updated

When you fix an issue:
1. Document the solution in [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Update [Fixes Applied](FIXES_APPLIED.md) with what changed
3. Keep [Quick Start Guide](QUICK_START.md) current

---

**Last Updated**: July 23, 2026  
**Documentation Version**: 1.0  
**Status**: Current ✅
