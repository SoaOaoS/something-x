{
  description = "Something X — Linux companion app for Nothing and CMF Bluetooth devices";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        python = pkgs.python3;

        somethingX = python.pkgs.buildPythonApplication {
          pname = "something-x";
          version = "1.0.0";
          pyproject = true;

          src = ./.;

          build-system = with python.pkgs; [ 
            setuptools 
            setuptools-scm
            wheel 
          ];

          dependencies = with python.pkgs; [
            pygobject3
            dbus-python
            pycairo
          ];

          nativeBuildInputs = with pkgs; [
            wrapGAppsHook4
            gobject-introspection
          ];

          buildInputs = with pkgs; [
            gtk4
            libadwaita
            bluez
            libnotify
          ];

          postInstall = ''
            install -Dm644 nothing_app/data/com.something.x.omarchy.desktop \
              $out/share/applications/com.something.x.omarchy.desktop
          '';

          meta = {
            description = "Linux companion app for Nothing and CMF Bluetooth devices";
            homepage = "https://github.com/SoaOaoS/something-x";
            license = pkgs.lib.licenses.mit;
            mainProgram = "something-x";
          };
        };
      in
      {
        packages.default = somethingX;
        packages.something-x = somethingX;

        devShells.default = pkgs.mkShell {
          inputsFrom = [ somethingX ];
          packages = [ pkgs.bluez-tools ];
        };
      }
    );
}
