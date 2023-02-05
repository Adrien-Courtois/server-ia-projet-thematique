# Serveur de traitement d'image

## Installation

Il suffit de récupérer le projet
```
git clone https://github.com/Adrien-Courtois/server-ia-projet-thematique.git
```

Choisir le mode de communication (socket ou http)
```
git checkout http # Communication http entre la rasp et le serveur
```
ou
```
git checkout socket # Communication par socket entre la rasp et le serveur
```

Installer les requirements python
```
pip install -r requirements.txt
```

Modifier le ficiher de configuration
```
nano .env
```

Lancer le serveur
```
python3 server.py
```