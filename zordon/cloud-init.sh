#cloud-config
package_update: true
package_upgrade: true

runcmd:
  # Instalar k3s
  - curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode=644" sh -

  # Espera a que arranque
  - sleep 15

  # Namespaces
  - k3s kubectl create namespace kafka
  - k3s kubectl create namespace remedios

  # Certificado autofirmado para remedios.midominio.com (ajusta CN/SAN si usas otro dominio)
  - mv remedios.cnf /etc/ssl/remedios.cnf
  - openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/remedios.key -out /etc/ssl/remedios.crt -config /etc/ssl/remedios.cnf

  # Secret TLS (idempotente)
  - k3s kubectl -n remedios create secret tls remedios-tls --cert=/etc/ssl/remedios.crt --key=/etc/ssl/remedios.key --dry-run=client -o yaml | k3s kubectl apply -f -

  # Aplicar YAMLs
  - k3s kubectl apply -f kafka.yaml
  - k3s kubectl apply -f remedios.yaml
