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

  # Aplicar YAMLs desde tu repo
  - curl -L https://raw.githubusercontent.com/TUUSER/TUREPO/main/kafka.yaml | k3s kubectl apply -f -
  - curl -L https://raw.githubusercontent.com/TUUSER/TUREPO/main/remedios.yaml | k3s kubectl apply -f -
