{ lib, stdenv, cups, python3, file }:

stdenv.mkDerivation {
  pname = "dcp-j315w-cups";
  version = lib.removeSuffix "\n" (builtins.readFile ../VERSION);
  # Select only build/check inputs; never copy local binaries or release assets
  # into the Nix store as source material.
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../rastertodcpj315w.c ../colour600_table.h ../build.sh
      ../DCP-J315W-CUPS.ppd.in ../LICENSE ../VERSION
      ../prologue_a4_150.bin ../prologue_a4_300.bin ../prologue_a4_600.bin
      ../prologue_a5_300.bin ../prologue_a5_600.bin
      ../prologue_a6_150.bin ../prologue_a6_300.bin ../prologue_a6_600.bin
      ../prologue_letter_300.bin ../prologue_letter_600.bin
      ../test_reliability.py ../test_discovery.py ../test_status.py
      ../test_geometry.py ../inspect_protocol.py ../make_geometry_probe.c
      ../discover.sh ../status_parse.awk ../fixtures
    ];
  };
  strictDeps = true;
  nativeBuildInputs = [ (lib.getDev cups) ];
  buildInputs = [ (lib.getLib cups) ];
  nativeCheckInputs = [ python3 file ];
  dontConfigure = true;
  buildPhase = ''
    runHook preBuild
    ./build.sh
    runHook postBuild
  '';
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    python3 test_reliability.py
    python3 test_discovery.py
    python3 test_status.py
    cc -std=c11 -Wall -Wextra -Werror make_geometry_probe.c $(cups-config --cflags --ldflags --libs) -o make_geometry_probe
    python3 test_geometry.py "$PWD/make_geometry_probe"
    runHook postCheck
  '';
  installPhase = ''
    runHook preInstall
    filterDir="$out/lib/cups/filter/dcp-j315w-cups"
    install -d "$filterDir" "$out/share/cups/model/dcp-j315w-cups" "$out/share/doc/dcp-j315w-cups"
    install -m755 rastertodcpj315w "$filterDir/"
    install -m644 prologue_*.bin "$filterDir/"
    sed "s|@FILTER@|$filterDir/rastertodcpj315w|" DCP-J315W-CUPS.ppd.in > "$out/share/cups/model/dcp-j315w-cups/DCP-J315W-CUPS.ppd"
    install -m644 LICENSE "$out/share/doc/dcp-j315w-cups/"
    runHook postInstall
  '';
  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    DCPJ315W_FILTER="$out/lib/cups/filter/dcp-j315w-cups/rastertodcpj315w" python3 test_reliability.py
    runHook postInstallCheck
  '';
  meta = {
    description = "Independent CUPS printing driver for the Brother DCP-J315W";
    homepage = "https://github.com/SolenMusic/dcp-j315w-cups";
    license = lib.licenses.mit;
    platforms = [ "x86_64-linux" "aarch64-linux" ];
  };
}
