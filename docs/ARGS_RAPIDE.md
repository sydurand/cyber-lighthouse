# Arguments Rapides 🎯

Contrôlez l'affichage dans la console avec des arguments simples.

## real_time.py

```bash
python real_time.py              # Normal (INFO level)
python real_time.py -v           # Verbose (DEBUG level)
python real_time.py -q           # Quiet (seulement les alertes)
python real_time.py -h           # Aide
```

## daily_time.py

```bash
python daily_time.py             # Normal (logs + rapport)
python daily_time.py -v          # Verbose (DEBUG + rapport)
python daily_time.py -q          # Quiet (rapport seulement)
python daily_time.py --json      # Format JSON
python daily_time.py -h          # Aide
```

## Cas d'Utilisation

### Développement - Voir tous les détails
```bash
python real_time.py -v
```

### Production - Affichage équilibré
```bash
python real_time.py
```

### Capturer un rapport propre
```bash
python daily_time.py -q > rapport.txt
```

### Format JSON pour API
```bash
python daily_time.py --json > data.json
```

### Monitoring avec logs
```bash
python real_time.py -v 2>&1 | tee monitoring.log
```

### Voir seulement les alertes
```bash
python real_time.py -q 2>&1 | grep ALERT
```

## Comparaison

| Commande | Affiche | Usage |
|----------|---------|-------|
| `python real_time.py` | INFO + alertes | Production normal |
| `python real_time.py -v` | DEBUG + tout | Debug/dev |
| `python real_time.py -q` | Alertes seulement | Silencieux |
| `python daily_time.py` | Logs + rapport | Voir résultat |
| `python daily_time.py -q` | Rapport seulement | Propre |
| `python daily_time.py --json` | JSON structuré | Automatisation |

Voilà! C'est simple! 🚀
