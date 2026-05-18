Pacote AUR: agildocheats

1. Publicar no GitHub primeiro (etiqueta v1.0.3 = version.txt):
     cd /home/agildo/AgildoCheats
     ./packaging/publicar-no-github.sh

2. AUR:
     cd packaging/aur
     chmod +x prepare-for-aur.sh enviar-para-aur.sh
     ./prepare-for-aur.sh
     makepkg -fci
     ./enviar-para-aur.sh

3. Instalar:
     paru -S agildocheats
