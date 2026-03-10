#include "args.h"
#include "logger.h"
#include <cstring>
#include <cstdio>

bool ParseArgs(int argc, char* argv[], Args& out)
{
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--scene") == 0) {
            if (++i >= argc) {
                fprintf(stderr, "[ERROR] --scene requires a path argument\n");
                return false;
            }
            out.scene_path = argv[i];
        }
        else if (strcmp(argv[i], "--output") == 0) {
            if (++i >= argc) {
                fprintf(stderr, "[ERROR] --output requires a path argument\n");
                return false;
            }
            out.output_override = argv[i];
        }
        else if (strcmp(argv[i], "--transparent") == 0) {
            out.transparent_override = true;
        }
        else if (strcmp(argv[i], "--inspect") == 0) {
            out.inspect = true;
        }
        else if (strcmp(argv[i], "--model") == 0) {
            if (++i >= argc) {
                fprintf(stderr, "[ERROR] --model requires a model id\n");
                return false;
            }
            out.inspect_model = argv[i];
        }
        else if (strcmp(argv[i], "--log-level") == 0) {
            if (++i >= argc) {
                fprintf(stderr, "[ERROR] --log-level requires a value\n");
                return false;
            }
            const char* lv = argv[i];
            if      (strcmp(lv, "error") == 0) out.log_level = LogLevel::Error;
            else if (strcmp(lv, "warn")  == 0) out.log_level = LogLevel::Warn;
            else if (strcmp(lv, "info")  == 0) out.log_level = LogLevel::Info;
            else if (strcmp(lv, "debug") == 0) out.log_level = LogLevel::Debug;
            else {
                fprintf(stderr, "[ERROR] Unknown log level \"%s\" — valid: error warn info debug\n", lv);
                return false;
            }
        }
        else {
            fprintf(stderr, "[ERROR] Unknown argument \"%s\"\n", argv[i]);
            return false;
        }
    }

    if (out.inspect) {
        if (out.inspect_model.empty()) {
            fprintf(stderr, "[ERROR] --inspect requires --model <id>\n");
            return false;
        }
        return true;  // skip --scene requirement for inspect mode
    }

    if (out.scene_path.empty()) {
        fprintf(stderr, "[ERROR] --scene <path> is required\n");
        fprintf(stderr, "Usage: live2d-render --scene <manifest.json> [--output <file>] [--transparent] [--log-level error|warn|info|debug]\n");
        fprintf(stderr, "       live2d-render --inspect --model <id>\n");
        return false;
    }

    return true;
}
