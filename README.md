# RootAlert

RootAlert est un mini-agent qui surveille les logs d'authentification Linux
(`/var/log/auth.log`) et envoie une alerte Telegram dès qu'un accès root/sudo
est détecté (connexion SSH ou commande sudo).