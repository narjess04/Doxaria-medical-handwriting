---
title: MediTrust API
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# MediTrust API

API du projet MediTrust (ESPRIT × Doxaria) : classification ordonnance / bulletin
(CNN), détection YOLOv8, lecture des ordonnances manuscrites (TrOCR fine-tuné),
vérification des médicaments dans les référentiels tunisiens et assistant (RAG).

Documentation interactive : `/docs`. Les routes, sauf `/api/health`, demandent
le jeton d'accès du frontend.
