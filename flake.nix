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
        python = pkgs.python3;
        pythonPackages = python.pkgs;
        pythonEnv = python.withPackages (pyPkgs: with pyPkgs; [
          python-ffmpeg
          hatchling
          ffmpeg-python
          pytest
        ]);
        normalize-mp4 = pythonPackages.buildPythonApplication {
          pname = "normalize-mp4";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";
          nativeBuildInputs = [ pythonPackages.hatchling ];
          propagatedBuildInputs = [ pythonPackages.ffmpeg-python ];
          nativeCheckInputs = [ pythonPackages.pytest pkgs.ffmpeg ];
          doCheck = true;
          checkPhase = ''
            pytest
          '';
          postInstall = let
            sitePackages = "${python.sitePackages}";
            pythonExe = "${python.executable}";
            ffmpegSite = "${pythonPackages.ffmpeg-python}/${python.sitePackages}";
          in ''
            runHook prePyz

            staging=$(mktemp -d)
            cp -a $out/${sitePackages}/normalize_mp4 $staging/
            cp -a $out/${sitePackages}/normalize_mp4-*.dist-info $staging/
            cp -a "${ffmpegSite}/ffmpeg" "$staging/"
            cp -a "${ffmpegSite}"/ffmpeg_python-*.dist-info "$staging/"

            chmod -R u+w "$staging"

            # Remove __pycache__ directories to keep the archive small.
            find "$staging" -type d -name "__pycache__" -prune -exec rm -rf {} +

            epoch="${SOURCE_DATE_EPOCH:-315532800}"
            find "$staging" -exec touch -h -d "@$epoch" {} +

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
          packages = [
            pythonEnv
            pkgs.ffmpeg
          ];
        };
      });
}
