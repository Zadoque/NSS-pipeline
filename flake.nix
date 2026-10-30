{
  description = "Ambiente de desenvolvimento do NSS Pipeline";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = forAllSystems (pkgs:
        let
          # O Dockerfile usa Python 3.12. O PySUS e o mutmut não estão
          # disponíveis de forma consistente no nixpkgs, por isso são
          # instalados no ambiente virtual pelo shellHook.
          python = pkgs.python312.withPackages (ps: with ps; [
            pip
            setuptools
            wheel
          ]);
        in {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.git
              pkgs.gnumake
              pkgs.pkg-config
              pkgs.gcc
              pkgs.stdenv.cc.cc.lib
              pkgs.openssl
              pkgs.postgresql
              pkgs.docker
              pkgs.docker-compose
            ];

            shellHook = ''
              export NSS_REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
              export VIRTUAL_ENV="$NSS_REPO_ROOT/.venv"
              export PIP_DISABLE_PIP_VERSION_CHECK=1
              export PYTHONUNBUFFERED=1
              export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

              if [ ! -x "$VIRTUAL_ENV/bin/python" ]; then
                ${python}/bin/python -m venv "$VIRTUAL_ENV"
              fi

              . "$VIRTUAL_ENV/bin/activate"

              # Reinstala somente quando os arquivos de dependência mudarem.
              nss_requirements_hash="$({ sha256sum "$NSS_REPO_ROOT/requirements.txt"; sha256sum "$NSS_REPO_ROOT/requirements-dev.txt"; } | sha256sum | cut -d' ' -f1)"
              nss_requirements_stamp="$VIRTUAL_ENV/.requirements-$nss_requirements_hash"
              if [ ! -f "$nss_requirements_stamp" ]; then
                python -m pip install -r "$NSS_REPO_ROOT/requirements.txt" \
                  -r "$NSS_REPO_ROOT/requirements-dev.txt"
                find "$VIRTUAL_ENV" -maxdepth 1 -name '.requirements-*' -type f -delete
                touch "$nss_requirements_stamp"
              fi

              export PYTHONPATH="$NSS_REPO_ROOT''${PYTHONPATH:+:$PYTHONPATH}"
              export PGHOST="''${PGHOST:-localhost}"
              export PGPORT="''${PGPORT:-5432}"

              echo "NSS Pipeline dev shell ativo: Python $(python --version 2>&1)"
              echo "Testes unitários: pytest -q"
              echo "PostgreSQL via Docker: docker compose up -d db"
            '';
          };
        });
    };
}
