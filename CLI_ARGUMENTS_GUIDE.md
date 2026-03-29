# Guide des Arguments de Ligne de Commande

Comment utiliser les arguments pour contrôler l'affichage dans la console.

## Arguments Disponibles

### real_time.py

```bash
python real_time.py [OPTIONS]
```

**Options:**
- `-v, --verbose` - Affiche tous les détails (niveau DEBUG)
- `-q, --quiet` - Sortie minimale (seulement erreurs et alertes)
- `-h, --help` - Affiche l'aide

**Exemples:**

```bash
# Mode normal (INFO level)
python real_time.py

# Mode détaillé (DEBUG level)
python real_time.py --verbose
python real_time.py -v

# Mode silencieux (WARNING level)
python real_time.py --quiet
python real_time.py -q

# Afficher l'aide
python real_time.py --help
python real_time.py -h
```

### daily_time.py

```bash
python daily_time.py [OPTIONS]
```

**Options:**
- `-v, --verbose` - Affiche tous les détails (niveau DEBUG)
- `-q, --quiet` - Sortie minimale (seulement le rapport)
- `--json` - Sortie au format JSON
- `-h, --help` - Affiche l'aide

**Exemples:**

```bash
# Mode normal avec logs
python daily_time.py

# Mode détaillé avec DEBUG
python daily_time.py --verbose
python daily_time.py -v

# Seulement le rapport (pas les logs)
python daily_time.py --quiet
python daily_time.py -q

# Sortie JSON
python daily_time.py --json

# Afficher l'aide
python daily_time.py --help
python daily_time.py -h
```

## Comparaison des Niveaux

### real_time.py - Mode Normal

```bash
python real_time.py
```

**Affichage:**
```
2026-03-30 12:34:56 - cyber_lighthouse - INFO - Starting real-time RSS monitoring...
2026-03-30 12:34:56 - cyber_lighthouse - INFO - Processing feed: BleepingComputer
2026-03-30 12:34:57 - cyber_lighthouse - INFO - New article detected: CVE-2024-XXXXX...
🚨 **ALERT**: Critical vulnerability in Apache Log4j
💥 **IMPACT**: Millions of systems affected
🏷️ **TAGS**: #CVE-2024-50001 #RCE
...
```

### real_time.py - Mode Verbose

```bash
python real_time.py --verbose
```

**Affichage (inclut DEBUG):**
```
2026-03-30 12:34:56 - cyber_lighthouse - INFO - Verbose mode enabled
2026-03-30 12:34:56 - cyber_lighthouse - DEBUG - Fetching RSS feed: BleepingComputer
2026-03-30 12:34:56 - cyber_lighthouse - DEBUG - Feed parsing warning for BleepingComputer
2026-03-30 12:34:57 - cyber_lighthouse - DEBUG - Cache miss for article: CVE-2024-XXXXX...
2026-03-30 12:34:57 - cyber_lighthouse - DEBUG - Sending article to Gemini for analysis
2026-03-30 12:34:58 - cyber_lighthouse - DEBUG - Article added: CVE-2024-XXXXX...
2026-03-30 12:34:58 - cyber_lighthouse - INFO - New article detected: CVE-2024-XXXXX...
...
```

### real_time.py - Mode Quiet

```bash
python real_time.py --quiet
```

**Affichage (seulement WARNING et ERROR):**
```
🚨 **ALERT**: Critical vulnerability
💥 **IMPACT**: Millions of systems
🏷️ **TAGS**: #CVE-2024-50001
```

### daily_time.py - Mode Normal

```bash
python daily_time.py
```

**Affichage:**
```
2026-03-30 12:35:00 - cyber_lighthouse - INFO - Starting daily synthesis...
2026-03-30 12:35:00 - cyber_lighthouse - INFO - Found 10 unprocessed articles
2026-03-30 12:35:01 - cyber_lighthouse - INFO - Fetching CISA KEV context...
2026-03-30 12:35:02 - cyber_lighthouse - INFO - Generating synthesis report...

======================================================================
# 🛑 DAILY SYNTHESIS REPORT

## 🌐 SECTION 1: STRATEGIC OVERVIEW
- **Executive Summary**: Multiple critical vulnerabilities identified...
...
======================================================================
```

### daily_time.py - Mode Verbose

```bash
python daily_time.py --verbose
```

**Affichage (inclut DEBUG):**
```
2026-03-30 12:35:00 - cyber_lighthouse - INFO - Verbose mode enabled
2026-03-30 12:35:00 - cyber_lighthouse - DEBUG - Loaded cache with 24 entries
2026-03-30 12:35:00 - cyber_lighthouse - INFO - Starting daily synthesis...
2026-03-30 12:35:00 - cyber_lighthouse - DEBUG - Retrieved 10 unprocessed articles
2026-03-30 12:35:01 - cyber_lighthouse - INFO - Fetching CISA KEV context...
2026-03-30 12:35:01 - cyber_lighthouse - DEBUG - Fetching RSS feed: CISA
2026-03-30 12:35:02 - cyber_lighthouse - DEBUG - Cache hit for synthesis report (saved 1 API call)
...
```

### daily_time.py - Mode Quiet

```bash
python daily_time.py --quiet
```

**Affichage (seulement le rapport):**
```
# 🛑 DAILY SYNTHESIS REPORT

## 🌐 SECTION 1: STRATEGIC OVERVIEW
- **Executive Summary**: Multiple critical vulnerabilities identified...
- **Key Trends**: Ransomware, supply chain attacks, zero-days

## 🛠️ SECTION 2: CRITICAL TECHNICAL ALERTS
- **Vulnerabilities**: CVE-2024-50001, CVE-2024-48005, CVE-2024-99999
- **TTPs**: Privilege escalation, credential theft, lateral movement
- **IOCs**: 10.0.0.0/24, evil.com, badmalware.exe
```

### daily_time.py - Mode JSON

```bash
python daily_time.py --json
```

**Affichage (JSON):**
```json
{
  "status": "success",
  "articles_count": 10,
  "report": "# 🛑 DAILY SYNTHESIS REPORT\n\n## 🌐 SECTION 1...",
  "timestamp": "2026-03-30T12:35:02.123456"
}
```

## Cas d'Utilisation

### 1. Développement / Debugging

```bash
# Voir tous les détails pour comprendre ce qui se passe
python real_time.py --verbose
python daily_time.py --verbose
```

Affiche:
- Messages DEBUG
- Traces des appels API
- Hits du cache
- Détails des requêtes

### 2. Production - Surveillance

```bash
# Affichage normal pour voir l'état du système
python real_time.py
python daily_time.py
```

Affiche:
- Messages INFO
- Nouvelles alertes
- Résumés
- Erreurs

### 3. Production - Silencieux

```bash
# Seulement les résultats importants
python real_time.py --quiet
python daily_time.py --quiet
```

Affiche:
- Seulement les alertes réelles
- Seulement le rapport final
- Erreurs si présentes

### 4. Rapports Automatisés

```bash
# Format JSON pour traitement automatique
python daily_time.py --json > rapport.json

# Traiter avec jq
cat rapport.json | jq '.report' > rapport.txt
```

### 5. Logging dans Fichier + Console

```bash
# Normal: logs dans console ET fichier
python real_time.py > console.log 2>&1

# Verbose: plus de détails
python real_time.py --verbose 2>&1 | tee execution.log

# Quiet: seulement les résultats
python daily_time.py --quiet 2>&1 | tee results.log
```

## Combinaisons d'Arguments

### Voir uniquement les erreurs

```bash
python real_time.py --quiet
# Output: Seulement les erreurs (WARNING, ERROR)
```

### Déboguer un problème

```bash
python real_time.py --verbose 2>&1 | tee debug.log
# Voir tous les détails et sauvegarder dans fichier
```

### Générer un rapport JSON

```bash
python daily_time.py --json | python -m json.tool
# Rapport structuré et formaté
```

### Combiner avec filtrage

```bash
# Seulement les alertes CRITIQUES
python real_time.py --quiet 2>&1 | grep "CRITICAL\|ERROR"

# Voir cache hits
python daily_time.py --verbose 2>&1 | grep -i "cache"

# Voir appels API
python daily_time.py --verbose 2>&1 | grep "API call\|saved"
```

## Exemples Pratiques

### Tester le système

```bash
# 1. Seed base de données
python seed_database.py --clear

# 2. Run en mode verbose pour voir tout
python real_time.py --verbose

# 3. Generate report en mode quiet
python daily_time.py --quiet

# 4. Check API usage
python daily_time.py --verbose 2>&1 | grep "saved"
```

### Automatisation avec cron

```bash
# Normal: logs dans journal
*/30 * * * * cd /path && python real_time.py >> /var/log/cyber-lighthouse.log 2>&1

# Quiet: résultats seulement
*/30 * * * * cd /path && python real_time.py --quiet >> /var/log/alerts.log 2>&1

# JSON: pour traitement
0 8 * * * cd /path && python daily_time.py --json >> /var/log/daily-report.json
```

### Surveillance en temps réel

```bash
# Afficher et sauvegarder
python real_time.py --verbose 2>&1 | tee -a monitoring.log

# Follow en temps réel
tail -f monitoring.log | grep "New article\|ALERT"
```

## Niveaux de Log

| Argument | Niveau | Affiche |
|----------|--------|---------|
| (default) | INFO | INFO, WARNING, ERROR |
| `-v, --verbose` | DEBUG | DEBUG, INFO, WARNING, ERROR |
| `-q, --quiet` | WARNING | WARNING, ERROR |

## Syntaxe et Combinaisons

```bash
# Formes courtes
python real_time.py -v
python daily_time.py -q

# Formes longues
python real_time.py --verbose
python daily_time.py --quiet

# Combinaisons valides
python daily_time.py --verbose --json  # Non recommandé: verbose + json
python daily_time.py --quiet           # OK: seulement rapport

# Non valide
python real_time.py --verbose --quiet  # Contradiction!
```

## FAQ

### Q: Où vont les logs s'ils ne s'affichent pas?

A: Dans le fichier `logs/cyber_lighthouse.log`

```bash
# Voir les logs
tail logs/cyber_lighthouse.log

# Suivre en temps réel
tail -f logs/cyber_lighthouse.log
```

### Q: Comment capturer la sortie dans un fichier?

A:
```bash
# Standard output
python real_time.py > output.txt

# Avec erreurs
python real_time.py > output.txt 2>&1

# Ajouter au fichier
python real_time.py >> output.txt 2>&1

# Afficher ET sauvegarder
python real_time.py | tee output.txt
```

### Q: Comment filtrer la sortie?

A:
```bash
# Seulement les alertes
python real_time.py 2>&1 | grep "ALERT\|CRITICAL"

# Seulement les erreurs
python real_time.py 2>&1 | grep "ERROR"

# Exclure les debug
python real_time.py 2>&1 | grep -v "DEBUG"
```

### Q: Quelle est la différence entre --verbose et --quiet?

A:
- `--verbose`: Affiche PLUS (inclut DEBUG)
- `--quiet`: Affiche MOINS (exclut INFO)
- Normal: Affichage équilibré (INFO + WARNING + ERROR)

### Q: Comment faire un rapport JSON programmatiquement?

A:
```bash
# Générer JSON
python daily_time.py --json > report.json

# Parser avec Python
python -c "import json; r = json.load(open('report.json')); print(r['report'])"

# Parser avec jq
cat report.json | jq '.report'
```

## Résumé

**Modes disponibles:**

```bash
python real_time.py              # Normal
python real_time.py -v           # Verbose (DEBUG)
python real_time.py -q           # Quiet (WARNING only)
python real_time.py -h           # Help

python daily_time.py             # Normal
python daily_time.py -v          # Verbose (DEBUG)
python daily_time.py -q          # Quiet (rapport only)
python daily_time.py --json      # JSON output
python daily_time.py -h          # Help
```

Utilisez les arguments pour contrôler exactement ce que vous voyez! 🎯
