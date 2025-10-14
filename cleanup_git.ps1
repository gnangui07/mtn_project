# Script pour nettoyer les fichiers sensibles de Git
Write-Host "Nettoyage des fichiers sensibles de Git..." -ForegroundColor Yellow

# 1. Supprimer .env de Git (mais le garder localement)
Write-Host "Suppression de .env..." -ForegroundColor Cyan
git rm --cached report/.env 2>$null
if ($?) { Write-Host ".env supprime de Git" -ForegroundColor Green }

# 2. Supprimer db.sqlite3 de Git
Write-Host "Suppression de db.sqlite3..." -ForegroundColor Cyan
git rm --cached report/db.sqlite3 2>$null
if ($?) { Write-Host "db.sqlite3 supprime de Git" -ForegroundColor Green }

# 3. Supprimer tous les __pycache__
Write-Host "Suppression des __pycache__..." -ForegroundColor Cyan
git ls-files | Select-String "__pycache__" | ForEach-Object {
    git rm --cached $_ 2>$null
}
Write-Host "__pycache__ supprimes" -ForegroundColor Green

# 4. Supprimer tous les .pyc
Write-Host "Suppression des .pyc..." -ForegroundColor Cyan
git ls-files | Select-String "\.pyc$" | ForEach-Object {
    git rm --cached $_ 2>$null
}
Write-Host ".pyc supprimes" -ForegroundColor Green

# 5. Supprimer les logs d'emails
Write-Host "Suppression des logs d'emails..." -ForegroundColor Cyan
git rm --cached report/sent_emails/*.log 2>$null
Write-Host "Logs supprimes" -ForegroundColor Green

# 6. Ajouter .gitignore
Write-Host "Ajout du .gitignore..." -ForegroundColor Cyan
git add .gitignore
Write-Host ".gitignore ajoute" -ForegroundColor Green

Write-Host ""
Write-Host "Nettoyage termine !" -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT: Maintenant tu dois:" -ForegroundColor Yellow
Write-Host "1. Commit: git commit -m 'Add .gitignore and remove sensitive files'" -ForegroundColor White
Write-Host "2. Push: git push" -ForegroundColor White
Write-Host "3. CHANGER tes secrets dans .env (SECRET_KEY, DB_PASSWORD)" -ForegroundColor Red
