#!/usr/bin/env python3
"""Replay the real C++ datapoint parser, without a firmware toolchain.

Run: python3 tests/test_datapoints.py
Requires Python 3 and a C++17 compiler (CXX, default g++). Only ESPHome
transport/log scaffolding is stubbed; the parser body is extracted verbatim.
"""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

# Keep stubs limited to the types/helpers used by handle_datapoints_.
PREAMBLE = r'''
#include <cstdint>
#include <cstddef>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <vector>
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGV(...) ((void)0)
static uint32_t encode_uint32(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
  return (uint32_t(a) << 24) | (uint32_t(b) << 16) | (uint32_t(c) << 8) | d;
}
'''
HARNESS = r'''
class Dreo {
 public:
  std::vector<uint8_t> ignore_mcu_update_on_datapoints_;
  std::vector<DreoDatapoint> datapoints_;
  std::vector<DreoDatapointListener> listeners_;
  void handle_datapoints_(const uint8_t *, size_t);
};
static void check(bool ok, const char *message) {
  if (!ok) {
    std::cerr << message << std::endl;
    std::exit(1);
  }
}
'''


def main():
    source = (ROOT / "components/dreo/dreo.cpp").read_text(encoding="utf-8-sig")
    method = source[source.index("void Dreo::handle_datapoints_("):
                    source.index("void Dreo::send_raw_command_(")]
    header = (ROOT / "components/dreo/dreo.h").read_text(encoding="utf-8-sig")
    types = header[header.index("enum class DreoDatapointType"):
                   header.index("enum class DreoCommandType")]
    fixtures = json.loads((ROOT / "protocol/dr-haf004s/status-reports.json").read_text())
    cases = []
    for fixture in fixtures:
        frame = bytes.fromhex(fixture["frame"])
        assert frame[:2] == b"\x55\xaa" and frame[4] == 0x07
        assert len(frame) == 9 + int.from_bytes(frame[6:8], "big")
        assert sum(frame[:-1]) % 256 == frame[-1], fixture["label"]
        values = ",".join(str(value) for value in frame[8:-1])
        cases.append('''{
          Dreo d;
          std::vector<uint8_t> payload = {VALUES};
          int speed = -1, oscillation = -1;
          d.listeners_ = {
            {4, [&](DreoDatapoint dp) { speed = dp.value_enum; }},
            {24, [&](DreoDatapoint dp) { oscillation = dp.value_enum; }}
          };
          d.handle_datapoints_(payload.data(), payload.size());
          check(speed == SPEED, "LABEL: speed after string DP lost");
          check(oscillation == OSC, "LABEL: oscillation after string DP lost");
        }'''.replace("VALUES", values)
             .replace("SPEED", str(fixture["speed"]))
             .replace("OSC", str(fixture["oscillation"]))
             .replace("LABEL", fixture["label"]))

    cases.extend([
        # Unknown non-string types retain upstream's warning-and-stop behavior.
        '''{ Dreo d; std::vector<uint8_t> b = {3,0,127,0,2,0,1,24,0,4,0,1,3};
          d.handle_datapoints_(b.data(),b.size());
          check(d.datapoints_.empty(),
                "Unknown non-string type must still stop the report"); }''',
        # Header claims more bytes than remain; do not scan its data as headers.
        '''{ Dreo d; std::vector<uint8_t> b = {3,0,3,255,255,24,0,4,0,1,3};
          d.handle_datapoints_(b.data(),b.size());
          check(d.datapoints_.empty(), "Truncated DP must stop safely"); }''',
        '''{ Dreo d; std::vector<uint8_t> b = {3,0,3,0,0,24,0,4,0,1,2};
          d.handle_datapoints_(b.data(),b.size());
          check(d.datapoints_.size()==1 && d.datapoints_[0].value_enum==2,
                "Zero-length unknown DP must advance"); }''',
        '''{ Dreo d; d.ignore_mcu_update_on_datapoints_={24};
          std::vector<uint8_t> b = {3,0,3,0,1,65,24,0,4,0,1,2};
          d.handle_datapoints_(b.data(),b.size());
          check(d.datapoints_.empty(), "Ignore list behavior changed"); }''',
        # Existing boolean/integer/enum behavior without strings.
        '''{ Dreo d; std::vector<uint8_t> b = {
          1,0,1,0,1,1, 13,0,2,0,4,0,0,0,80, 4,0,4,0,1,9};
          d.handle_datapoints_(b.data(),b.size());
          check(d.datapoints_.size()==3 && d.datapoints_[0].value_bool &&
                d.datapoints_[1].value_uint==80 && d.datapoints_[2].value_enum==9,
                "Existing numeric decoding regressed"); }''',
        # Unsupported strings must not notify a numeric listener for that ID.
        '''{ Dreo d; int called=0;
          d.listeners_={{3,[&](DreoDatapoint){called++;}}};
          std::vector<uint8_t> b={3,0,3,0,1,65};
          d.handle_datapoints_(b.data(),b.size());
          check(called==0 && d.datapoints_.empty(),
                "Unsupported data must not reach numeric listeners"); }''',
    ])
    program = PREAMBLE + types + HARNESS + method + "\nint main() {\n"
    program += "\n".join(cases)
    program += '\nstd::cout << "PASS: ' + str(len(cases)) + ' parser cases\\n";\n}\n'
    # Place temporary files in the caller's configured temp directory.
    with tempfile.TemporaryDirectory(prefix="dreo-parser-") as tmp:
        cpp, exe = Path(tmp) / "parser.cpp", Path(tmp) / "parser"
        cpp.write_text(program)
        compiler = shlex.split(os.environ.get("CXX", "g++"))
        flags = shlex.split(os.environ.get("CXXFLAGS", ""))
        subprocess.run(compiler + ["-std=c++17"] + flags +
                       [str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
