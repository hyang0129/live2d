#include "logger.h"
#include <cstdarg>
#include <cstdio>

namespace Logger {

static LogLevel s_level = LogLevel::Info;
static FILE*    s_file  = nullptr;

void SetLevel(LogLevel level) { s_level = level; }
LogLevel GetLevel()           { return s_level; }

void OpenLogFile(const std::string& path)
{
    CloseLogFile();
    if (!path.empty())
        s_file = fopen(path.c_str(), "w");
}

void CloseLogFile()
{
    if (s_file) { fclose(s_file); s_file = nullptr; }
}

static void Print(const char* tag, const char* fmt, va_list args)
{
    // stderr
    fprintf(stderr, "[%s] ", tag);
    va_list args2;
    va_copy(args2, args);
    vfprintf(stderr, fmt, args2);
    va_end(args2);
    fprintf(stderr, "\n");

    // log file
    if (s_file) {
        fprintf(s_file, "[%s] ", tag);
        vfprintf(s_file, fmt, args);
        fprintf(s_file, "\n");
        fflush(s_file);
    }
}

void Error(const char* fmt, ...)
{
    va_list args; va_start(args, fmt);
    Print("ERROR", fmt, args);
    va_end(args);
}

void Warn(const char* fmt, ...)
{
    if (s_level < LogLevel::Warn) return;
    va_list args; va_start(args, fmt);
    Print("WARN ", fmt, args);
    va_end(args);
}

void Info(const char* fmt, ...)
{
    if (s_level < LogLevel::Info) return;
    va_list args; va_start(args, fmt);
    Print("INFO ", fmt, args);
    va_end(args);
}

void Debug(const char* fmt, ...)
{
    if (s_level < LogLevel::Debug) return;
    va_list args; va_start(args, fmt);
    Print("DEBUG", fmt, args);
    va_end(args);
}

} // namespace Logger
