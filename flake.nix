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
        python = pkgs.python311;
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
        };
      in {
        packages.default = normalize-mp4;
        devShells.default = pkgs.mkShell {
          packages = [
            python
            python.pkgs.hatch
            python.pkgs.ffmpeg-python
            python.pkgs.pytest
            pkgs.ffmpeg
          ];
        };
      }
    );
}
