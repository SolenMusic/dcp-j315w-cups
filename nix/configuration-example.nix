# Replace the checkout path and printer address before importing this module.
{ pkgs, ... }:
let
  driver = pkgs.callPackage /path/to/dcp-j315w-cups/nix { };
in {
  services.printing = {
    enable = true;
    drivers = [ driver ];
  };
  hardware.printers.ensurePrinters = [{
    name = "DCP_J315W";
    description = "DCP-J315W CUPS Driver";
    deviceUri = "socket://192.0.2.10:9100";
    model = "dcp-j315w-cups/DCP-J315W-CUPS.ppd";
    ppdOptions = {
      PageSize = "A4";
      Resolution = "300dpi";
      ColorModel = "Mono";
    };
  }];
}
