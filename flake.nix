{
  description = "normalize-mp4 Python project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python =
          pkgs.python3.withPackages (pyPkgs: with pyPkgs; [ python-ffmpeg ]);
        normalize-mp4 = python.pkgs.buildPythonApplication {
          pname = "normalize-mp4";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";
          nativeBuildInputs = [ python.pkgs.hatchling ];
          propagatedBuildInputs = [ python.pkgs.ffmpeg-python ];
          nativeCheckInputs = [ python.pkgs.pytest pkgs.ffmpeg ];
          doCheck = true;
          checkPhase = ''
            pytest
          '';
          postInstall = let
            sitePackages = "${python.sitePackages}";
            pythonExe = "${python.executable}";
          in ''
            runHook prePyz

            staging=$(mktemp -d)
            cp -a $out/${sitePackages}/normalize_mp4 $staging/
            cp -a $out/${sitePackages}/normalize_mp4-*.dist-info $staging/
            cp -a $out/${sitePackages}/ffmpeg $staging/
            cp -a $out/${sitePackages}/ffmpeg_python-*.dist-info $staging/

            # Remove __pycache__ directories to keep the archive small.
            find "$staging" -type d -name "__pycache__" -prune -exec rm -rf {} +

            mkdir -p "$out/bin"
            (cd "$staging" && ${pythonExe} -m zipapp . \
              -m normalize_mp4.__main__:main \
              -p "/usr/bin/env python3" \
              -o "$out/bin/normalize-mp4.pyz")

            rm -rf "$staging"

            # The wrapped console script provided by buildPythonApplication is not
            # needed once the self-contained zipapp has been produced.
            rm -f "$out/bin/normalize-mp4"

            runHook postPyz
          '';
        };
      in {
        packages.default = normalize-mp4;
        devShells.default = pkgs.mkShell {
          packages = with python.pkgs; [
            python
            hatchling
            ffmpeg-python
            pytest
            pkgs.ffmpeg
          ];
        };
      });
}
