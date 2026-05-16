# Agildo Cheats

Trainer de memória para **Linux** (PyQt6): scanner estilo Cheat Engine, congelar valores, importar tabelas `.CT` e teleporte de coordenadas.

**Versão da interface:** V15.3 · **Pacote:** 1.0.1

## Requisitos

- Python 3, `python-pyqt6`, `python-psutil`
- Acesso a `/proc/PID/mem` (muitas vezes `sudo` ou `ptrace_scope=0`)
- Opcional: `nvidia-utils` para GPU NVIDIA

## Executar do código

```bash
python agildo_cheats.py
```

## Instalação (Arch / CachyOS)

Depois de publicado na AUR:

```bash
paru -S agildocheats
```

Ou clone `ssh://aur@aur.archlinux.org/agildocheats.git` e `makepkg -si`.

## Uso responsável

Destinado a jogos **offline / single-player** onde a modificação é permitida. O autor não se responsabiliza por uso em jogos online ou violação de termos de serviço.

## Licença

Código sob GPL-3.0-or-later (ajustar se aplicares outra licença).
