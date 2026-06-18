# Full Stack Spotter Assessment

This repository contains the implementation of a full-stack engineering assessment.

The repository is divided into two main sections:

---

## 📁 1. `assessment/`

This directory contains the original assessment materials provided as part of the task:

- Requirements specification document
- Reference PDFs
- Supporting images and assets

These files define the functional scope and expected behavior of the application and are included for reference only.

---

## 🧩 2. `project/`

This directory contains the complete implementation of the solution.

It is a full-stack application composed of:

### Backend
- Built with **Django**
- REST API responsible for ELD log processing
- Provides endpoints used by the frontend for data retrieval and processing

### Frontend
- Built with **React (Vite)**
- Component-based UI for visualization of ELD logs
- Handles route visualization and rendering logic

---
## 🚀 Live Demo

- 🌐 Frontend (Live Web App with the production API): https://spotter-milad.onrender.com/
- 🔌 Backend RESTful API (POST Only): https://full-stack-spotter-assessment-1.onrender.com/api/eld/
- 📦 Github Repo: https://github.com/m11ad/full-stack-spotter-assessment/
- 📼 Explainer Video: https://www.loom.com/share/20c820338daf44ffa58b73331b4f8f22
---

## 🔁 Architecture Overview

The system follows a simple client–server architecture:

- The **frontend** communicates with the backend via REST APIs
- The **backend** processes and returns structured JSON responses
- The frontend is responsible for rendering and visualization only

This separation ensures clear boundaries between presentation and business logic.

---

## 🚀 Running the Application

All setup and execution instructions are located inside the `project/` directory.

Please refer to:
project/README.md

for detailed steps to run both backend and frontend services.

---

## 📌 Notes

- The `assessment/` folder contains only reference materials and is not part of the runnable application
- The `project/` folder contains the full working implementation
- Each service (frontend and backend) is independently runnable

---

## 🧠 Summary

This project demonstrates a modular full-stack implementation with a Django REST backend and a React (Vite) frontend, following a clear separation of concerns between data processing and UI rendering.
