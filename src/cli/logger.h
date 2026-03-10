#pragma once
#include <string>

enum class LogLevel { Error = 0, Warn, Info, Debug };

namespace Logger {

void SetLevel(LogLevel level);
LogLevel GetLevel();

// Tee all log output to a file in addition to stderr.
// Call after the output path is known. Pass "" to close.
void OpenLogFile(const std::string& path);
void CloseLogFile();

void Error(const char* fmt, ...);
void Warn (const char* fmt, ...);
void Info (const char* fmt, ...);
void Debug(const char* fmt, ...);

} // namespace Logger
