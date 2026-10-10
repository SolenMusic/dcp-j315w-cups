# NixOS

Use the native Nix recipe in `nix/default.nix`, rather than the binary tarball's
Bash installer. It builds the filter against Nix's CUPS library and installs its
printer command data beside the executable in the immutable Nix store. The PPD
references that exact store path.

## Build

With a configured Nixpkgs channel:

```sh
nix-build -E 'let pkgs = import <nixpkgs> {}; in pkgs.callPackage ./nix {}'
```

For the pinned CI baseline:

```sh
nix-build nix/ci.nix
```

Both x86_64-linux and aarch64-linux are supported build targets. The derivation
checks baseline output, malformed jobs, cancellation and geometry normalization;
it also executes the installed filter from its store path to verify command-data
lookup. Python is a build/check dependency, not a runtime dependency.

## Configure

Adapt `nix/configuration-example.nix`: replace the checkout path and documentation
address with your source location and actual printer address. Add the module to
your NixOS configuration's imports, then apply your normal `nixos-rebuild switch`.

The module uses `services.printing.drivers` and `hardware.printers.ensurePrinters`
to register the driver and network queue declaratively. It does not set a system
default printer. A fixed `socket://` address is used in the example; reserve that
address in your router if needed.

Only the DCP-J315W is supported, with the same paper/colour limitations as other
builds. Nix builds and store-path checks are automated; physical NixOS printing
and a complete NixOS VM deployment have not yet been tested. This recipe is part
of this repository and is not a claim that the driver has entered Nixpkgs.
