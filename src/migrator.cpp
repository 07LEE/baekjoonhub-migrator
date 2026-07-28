#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <sstream>
#include <fstream>
#include <filesystem>
#include <memory>
#include <cstdlib>
#include <cctype>
#include <cstring>
#include <functional>

#if defined(_WIN32) || defined(_WIN64)
#include <windows.h>
#define IS_WINDOWS 1
#else
#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>
#define IS_WINDOWS 0
#endif

namespace fs = std::filesystem;

// Check if path is a remote Git repository URL
bool is_remote_url(const std::string& path) {
    return path.rfind("http://", 0) == 0 ||
           path.rfind("https://", 0) == 0 ||
           path.rfind("git@", 0) == 0 ||
           path.rfind("ssh://", 0) == 0;
}

// Convert string to uppercase
std::string to_upper(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return std::toupper(c); });
    return s;
}

// Convert string to lowercase
std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return std::tolower(c); });
    return s;
}

// Trim leading and trailing whitespace / quotes
std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n\"'");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n\"'");
    return s.substr(start, end - start + 1);
}

class PathMapper {
public:
    static inline const std::unordered_map<std::string, std::string> LANGUAGE_EXTENSIONS = {
        {".py", "Python"},
        {".java", "Java"},
        {".cpp", "C++"},
        {".cc", "C++"},
        {".c", "C"},
        {".js", "JavaScript"},
        {".ts", "TypeScript"},
        {".kt", "Kotlin"},
        {".swift", "Swift"},
        {".rb", "Ruby"},
        {".go", "Go"},
        {".rs", "Rust"},
        {".sql", "SQL"},
        {".oracle", "Oracle"},
        {".mysql", "MySQL"},
        {".cs", "C#"},
        {".sh", "Bash"},
        {".gs", "Golfscript"}
    };

    static inline const std::unordered_set<std::string> PLATFORMS = {
        "백준", "프로그래머스", "SWEA", "goormlevel", "LEETCODE"
    };

    static inline std::unordered_map<std::string, std::string> SQL_CACHE;

    static std::string detect_sql_dialect(const std::string& content) {
        std::string upper_content = to_upper(content);
        std::vector<std::string> oracle_keywords = {
            "NVL", "SYSDATE", "TO_CHAR", "TO_DATE", "DECODE", "ROWNUM", "VARCHAR2", "NUMBER", "CONNECT BY"
        };
        std::vector<std::string> mysql_keywords = {
            "IFNULL", "DATE_FORMAT", "NOW()", "LIMIT", "CONCAT", "GROUP_CONCAT"
        };

        for (const auto& kw : oracle_keywords) {
            if (upper_content.find(kw) != std::string::npos) return "Oracle";
        }
        for (const auto& kw : mysql_keywords) {
            if (upper_content.find(kw) != std::string::npos) return "MySQL";
        }
        return "MySQL";
    }

    static std::string transform_path(
        const std::string& path,
        const std::string& mode,
        const std::function<std::string(const std::string&)>& content_getter = nullptr,
        const std::string& blob_sha = ""
    ) {
        std::string norm_path = path;
        std::replace(norm_path.begin(), norm_path.end(), '\\', '/');

        std::vector<std::string> parts;
        std::stringstream ss(norm_path);
        std::string part;
        while (std::getline(ss, part, '/')) {
            if (!part.empty()) parts.push_back(part);
        }

        if (parts.empty()) return path;

        std::string top_dir = parts[0];
        if (top_dir == "Python3") top_dir = "Python";

        std::vector<std::string> sub_parts(parts.begin() + 1, parts.end());

        // Find code file
        std::string code_file = "";
        for (auto it = parts.rbegin(); it != parts.rend(); ++it) {
            std::string lower_p = to_lower(*it);
            if (lower_p != "readme.md" && fs::path(*it).has_extension()) {
                code_file = *it;
                break;
            }
        }

        std::string detected_lang = "";
        if (!code_file.empty()) {
            std::string ext = to_lower(fs::path(code_file).extension().string());
            if (ext == ".sql") {
                if (!blob_sha.empty() && SQL_CACHE.count(blob_sha)) {
                    detected_lang = SQL_CACHE[blob_sha];
                } else if (content_getter && !blob_sha.empty()) {
                    try {
                        std::string content = content_getter(blob_sha);
                        detected_lang = detect_sql_dialect(content);
                        SQL_CACHE[blob_sha] = detected_lang;
                    } catch (...) {
                        detected_lang = "MySQL";
                    }
                } else {
                    detected_lang = "MySQL";
                }
            } else {
                auto it = LANGUAGE_EXTENSIONS.find(ext);
                if (it != LANGUAGE_EXTENSIONS.end()) {
                    detected_lang = it->second;
                }
            }
        }

        std::string lang = "";
        std::string platform = "";
        std::vector<std::string> rel_path_parts;

        // Case A: Top directory is language, sub directory is platform
        if (PLATFORMS.find(top_dir) == PLATFORMS.end() && !sub_parts.empty() && PLATFORMS.find(sub_parts[0]) != PLATFORMS.end()) {
            lang = !detected_lang.empty() ? detected_lang : top_dir;
            platform = sub_parts[0];
            rel_path_parts.assign(sub_parts.begin() + 1, sub_parts.end());
        }
        // Case B: Top directory is platform
        else if (PLATFORMS.find(top_dir) != PLATFORMS.end()) {
            platform = top_dir;
            lang = !detected_lang.empty() ? detected_lang : "Python";
            rel_path_parts = sub_parts;
        } else {
            return path;
        }

        // Normalize Programmers level folders
        if (platform == "프로그래머스" && !rel_path_parts.empty()) {
            std::string level_dir = rel_path_parts[0];
            std::string lower_level = to_lower(level_dir);
            if (lower_level.rfind("lv", 0) == 0) {
                std::string digits = level_dir.substr(2);
                bool all_digits = !digits.empty() && std::all_of(digits.begin(), digits.end(), ::isdigit);
                if (all_digits) {
                    rel_path_parts[0] = digits;
                }
            }
        }

        std::vector<std::string> new_parts;
        if (mode == "platform_first") {
            new_parts.push_back(platform);
            new_parts.insert(new_parts.end(), rel_path_parts.begin(), rel_path_parts.end());
        } else if (mode == "language_first") {
            new_parts.push_back(lang);
            new_parts.push_back(platform);
            new_parts.insert(new_parts.end(), rel_path_parts.begin(), rel_path_parts.end());
        } else {
            new_parts = parts;
        }

        std::string result = "";
        for (size_t i = 0; i < new_parts.size(); ++i) {
            if (i > 0) result += "/";
            result += new_parts[i];
        }
        return result;
    }
};

std::string unescape_path(const std::string& path_str) {
    if (path_str.length() >= 2 && path_str.front() == '"' && path_str.back() == '"') {
        std::string inner = path_str.substr(1, path_str.length() - 2);
        std::string result = "";
        size_t i = 0;
        size_t n = inner.length();
        while (i < n) {
            if (inner[i] == '\\' && i + 1 < n) {
                char next_char = inner[i + 1];
                if (std::isdigit(static_cast<unsigned char>(next_char)) && i + 3 < n &&
                    std::isdigit(static_cast<unsigned char>(inner[i + 2])) &&
                    std::isdigit(static_cast<unsigned char>(inner[i + 3]))) {
                    int octal_val = std::stoi(inner.substr(i + 1, 3), nullptr, 8);
                    result.push_back(static_cast<char>(octal_val));
                    i += 4;
                } else {
                    switch (next_char) {
                        case 'n': result.push_back('\n'); break;
                        case 't': result.push_back('\t'); break;
                        case 'v': result.push_back('\v'); break;
                        case 'b': result.push_back('\b'); break;
                        case 'r': result.push_back('\r'); break;
                        case 'f': result.push_back('\f'); break;
                        case 'a': result.push_back('\a'); break;
                        case '\\': result.push_back('\\'); break;
                        case '"': result.push_back('"'); break;
                        default: result.push_back(next_char); break;
                    }
                    i += 2;
                }
            } else {
                result.push_back(inner[i]);
                i += 1;
            }
        }
        return result;
    }
    return path_str;
}

std::string escape_path(const std::string& path_str) {
    bool needs_quoting = false;
    for (char c : path_str) {
        if (c == ' ' || c == '\t' || c == '\n' || c == '"' || c == '\\') {
            needs_quoting = true;
            break;
        }
    }
    if (!needs_quoting) return path_str;

    std::string escaped = "\"";
    for (char c : path_str) {
        if (c == '"') escaped += "\\\"";
        else if (c == '\\') escaped += "\\\\";
        else if (c == '\n') escaped += "\\n";
        else if (c == '\t') escaped += "\\t";
        else escaped.push_back(c);
    }
    escaped += "\"";
    return escaped;
}

// Git Rewriter Helper Functions
std::string run_git_command(const std::string& repo_dir, const std::vector<std::string>& args) {
    std::string cmd = "git -C \"" + repo_dir + "\"";
    for (const auto& arg : args) {
        cmd += " \"" + arg + "\"";
    }

#if IS_WINDOWS
    FILE* pipe = _popen(cmd.c_str(), "r");
#else
    FILE* pipe = popen(cmd.c_str(), "r");
#endif

    if (!pipe) return "";

    char buffer[4096];
    std::string result = "";
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }

#if IS_WINDOWS
    _pclose(pipe);
#else
    pclose(pipe);
#endif

    return result;
}

void preview_migration(const std::string& repo_dir, const std::string& mode) {
    std::string commits_out = run_git_command(repo_dir, {"log", "--reverse", "--format=%H"});
    std::stringstream ss(commits_out);
    std::vector<std::string> commits;
    std::string line;
    while (std::getline(ss, line)) {
        std::string t = trim(line);
        if (!t.empty()) commits.push_back(t);
    }

    if (commits.empty()) {
        std::cout << "[-] No commits found in repository.\n";
        return;
    }

    std::string latest_sha = commits.back();
    std::string tree_out = run_git_command(repo_dir, {"ls-tree", "-r", latest_sha});

    std::cout << "\n============================================================\n";
    std::cout << " DRY-RUN PREVIEW (Mode: " << mode << ")\n";
    std::cout << "============================================================\n";

    std::stringstream tss(tree_out);
    int count = 0;
    int changed_count = 0;
    int total_files = 0;

    auto content_getter = [&](const std::string& sha) -> std::string {
        return run_git_command(repo_dir, {"cat-file", "-p", sha});
    };

    while (std::getline(tss, line)) {
        if (line.empty()) continue;
        total_files++;
        size_t tab_pos = line.find('\t');
        if (tab_pos == std::string::npos) continue;

        std::string meta = line.substr(0, tab_pos);
        std::string path = line.substr(tab_pos + 1);

        std::stringstream mss(meta);
        std::string mode_str, item_type, sha;
        mss >> mode_str >> item_type >> sha;

        std::string new_path = PathMapper::transform_path(path, mode, content_getter, sha);
        if (count < 20) {
            if (new_path != path) {
                std::cout << " [MOVE] " << path << "\n     -> " << new_path << "\n";
                changed_count++;
            } else {
                std::cout << " [KEEP] " << path << "\n";
            }
            count++;
        }
    }

    std::cout << "\nSample preview completed. (" << changed_count << " files moved out of first " << count << " shown, " << total_files << " total files)\n";
    std::cout << "============================================================\n\n";
}

void execute_rewrite(const std::string& repo_dir, const std::string& mode) {
    std::string current_branch = trim(run_git_command(repo_dir, {"rev-parse", "--abbrev-ref", "HEAD"}));
    if (current_branch == "HEAD" || current_branch.empty()) {
        current_branch = "main";
    }

    std::cout << "[+] Starting Git history rewrite for branch '" << current_branch << "'...\n";

    // Create backup branch
    run_git_command(repo_dir, {"branch", "-D", "backup-before-migration"});
    run_git_command(repo_dir, {"branch", "backup-before-migration"});
    std::cout << "[+] Backup branch created: 'backup-before-migration'\n";

    std::string export_cmd = "git -C \"" + repo_dir + "\" fast-export \"" + current_branch + "\"";
    std::string import_cmd = "git -C \"" + repo_dir + "\" fast-import --force --quiet";

#if IS_WINDOWS
    FILE* exp_pipe = _popen(export_cmd.c_str(), "rb");
    FILE* imp_pipe = _popen(import_cmd.c_str(), "wb");

    if (!exp_pipe || !imp_pipe) {
        std::cerr << "[-] Error creating process pipe for fast-export/import.\n";
        return;
    }
#else
    int pipe_exp[2];
    int pipe_imp[2];

    if (pipe(pipe_exp) < 0 || pipe(pipe_imp) < 0) {
        std::cerr << "[-] Error creating POSIX pipes.\n";
        return;
    }

    pid_t pid_exp = fork();
    if (pid_exp == 0) {
        close(pipe_exp[0]);
        dup2(pipe_exp[1], STDOUT_FILENO);
        close(pipe_exp[1]);
        execlp("git", "git", "-C", repo_dir.c_str(), "fast-export", current_branch.c_str(), nullptr);
        exit(1);
    }

    pid_t pid_imp = fork();
    if (pid_imp == 0) {
        close(pipe_imp[1]);
        dup2(pipe_imp[0], STDIN_FILENO);
        close(pipe_imp[0]);
        execlp("git", "git", "-C", repo_dir.c_str(), "fast-import", "--force", "--quiet", nullptr);
        exit(1);
    }

    close(pipe_exp[1]);
    close(pipe_imp[0]);

    FILE* exp_pipe = fdopen(pipe_exp[0], "rb");
    FILE* imp_pipe = fdopen(pipe_imp[1], "wb");
#endif

    std::unordered_map<std::string, std::string> sql_blob_cache;
    enum State { FREE, BLOB_MARK, BLOB_DATA_HEADER, COMMIT };
    State state = FREE;
    std::string blob_mark = "";

    char line_buf[8192];
    while (fgets(line_buf, sizeof(line_buf), exp_pipe) != nullptr) {
        std::string line_str(line_buf);

        if (state == FREE) {
            if (line_str.rfind("blob\n", 0) == 0) {
                fputs(line_buf, imp_pipe);
                state = BLOB_MARK;
            } else if (line_str.rfind("commit ", 0) == 0) {
                fputs(line_buf, imp_pipe);
                state = COMMIT;
            } else {
                fputs(line_buf, imp_pipe);
            }
        } else if (state == BLOB_MARK) {
            fputs(line_buf, imp_pipe);
            if (line_str.rfind("mark ", 0) == 0) {
                blob_mark = trim(line_str.substr(5));
                state = BLOB_DATA_HEADER;
            } else {
                blob_mark = "";
                state = FREE;
            }
        } else if (state == BLOB_DATA_HEADER) {
            fputs(line_buf, imp_pipe);
            if (line_str.rfind("data ", 0) == 0) {
                size_t size = std::stoull(line_str.substr(5));
                std::string content(size, '\0');
                size_t bytes_read = fread(&content[0], 1, size, exp_pipe);
                fwrite(content.c_str(), 1, bytes_read, imp_pipe);

                int nl = fgetc(exp_pipe);
                if (nl != EOF) fputc(nl, imp_pipe);

                if (!blob_mark.empty() && size < 1024 * 1024) {
                    sql_blob_cache[blob_mark] = content;
                }
                blob_mark = "";
                state = FREE;
            } else {
                state = FREE;
            }
        } else if (state == COMMIT) {
            if (line_str.rfind("data ", 0) == 0) {
                fputs(line_buf, imp_pipe);
                size_t size = std::stoull(line_str.substr(5));
                std::string content(size, '\0');
                size_t bytes_read = fread(&content[0], 1, size, exp_pipe);
                fwrite(content.c_str(), 1, bytes_read, imp_pipe);

                int nl = fgetc(exp_pipe);
                if (nl != EOF) fputc(nl, imp_pipe);
            } else if (line_str.rfind("M ", 0) == 0) {
                std::string rest = line_str.substr(2);
                size_t sp1 = rest.find(' ');
                size_t sp2 = rest.find(' ', sp1 + 1);

                if (sp1 != std::string::npos && sp2 != std::string::npos) {
                    std::string fmode = rest.substr(0, sp1);
                    std::string dataref = rest.substr(sp1 + 1, sp2 - (sp1 + 1));
                    std::string raw_path = trim(rest.substr(sp2 + 1));

                    std::string orig_path = unescape_path(raw_path);
                    auto content_getter = [&](const std::string& sha) -> std::string {
                        auto it = sql_blob_cache.find(sha);
                        return (it != sql_blob_cache.end()) ? it->second : "";
                    };

                    std::string new_path = PathMapper::transform_path(orig_path, mode, content_getter, dataref);
                    std::string escaped_new = escape_path(new_path);

                    std::string new_line = "M " + fmode + " " + dataref + " " + escaped_new + "\n";
                    fputs(new_line.c_str(), imp_pipe);
                } else {
                    fputs(line_buf, imp_pipe);
                }
            } else if (line_str.rfind("D ", 0) == 0) {
                std::string raw_path = trim(line_str.substr(2));
                std::string orig_path = unescape_path(raw_path);
                std::string new_path = PathMapper::transform_path(orig_path, mode);
                std::string escaped_new = escape_path(new_path);
                std::string new_line = "D " + escaped_new + "\n";
                fputs(new_line.c_str(), imp_pipe);
            } else if (line_str.rfind("blob\n", 0) == 0) {
                fputs(line_buf, imp_pipe);
                state = BLOB_MARK;
            } else if (line_str.rfind("commit ", 0) == 0) {
                fputs(line_buf, imp_pipe);
                state = COMMIT;
            } else if (line_str.rfind("reset ", 0) == 0 || line_str.rfind("tag ", 0) == 0 || line_str.rfind("checkpoint\n", 0) == 0) {
                fputs(line_buf, imp_pipe);
                state = FREE;
            } else {
                fputs(line_buf, imp_pipe);
            }
        }
    }

#if IS_WINDOWS
    _pclose(exp_pipe);
    _pclose(imp_pipe);
#else
    fclose(exp_pipe);
    fclose(imp_pipe);
    waitpid(pid_exp, nullptr, 0);
    waitpid(pid_imp, nullptr, 0);
#endif

    run_git_command(repo_dir, {"checkout", "-f", current_branch});
    std::cout << "\n[+] Migration successfully finished! Branch '" << current_branch << "' now points to rewritten history.\n";
    std::cout << "[+] Original history backed up in 'backup-before-migration'.\n";
}

int main(int argc, char* argv[]) {
    std::string repo_input = fs::current_path().string();
    std::string mode = "";
    bool dry_run = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--repo" && i + 1 < argc) {
            repo_input = argv[++i];
        } else if (arg == "--mode" && i + 1 < argc) {
            mode = argv[++i];
        } else if (arg == "--dry-run") {
            dry_run = true;
        }
    }

    bool is_remote = is_remote_url(repo_input);
    std::string repo_dir = repo_input;
    std::string temp_dir = "";

    if (!is_remote) {
        repo_dir = fs::absolute(repo_input).string();
        if (!fs::exists(fs::path(repo_dir) / ".git")) {
            std::cout << "[*] Note: '" << repo_dir << "' is not a Git repository.\n";
            std::cout << "Please enter the path or URL to target Git repository: ";
            std::string user_repo;
            std::getline(std::cin, user_repo);
            user_repo = trim(user_repo);
            if (!user_repo.empty()) {
                if (is_remote_url(user_repo)) {
                    is_remote = true;
                    repo_input = user_repo;
                } else {
                    repo_dir = fs::absolute(user_repo).string();
                }
            }
        }
    }

    if (!is_remote && !fs::exists(fs::path(repo_dir) / ".git")) {
        std::cerr << "[-] Error: '" << repo_dir << "' is not a valid Git repository.\n";
        return 1;
    }

    if (is_remote) {
        temp_dir = (fs::temp_directory_path() / ("bjhub_migrator_cpp_" + std::to_string(std::rand()))).string();
        std::cout << "[+] Cloning remote repository from '" << repo_input << "'...\n";
        std::string clone_cmd = "git clone \"" + repo_input + "\" \"" + temp_dir + "\"";
        int res = std::system(clone_cmd.c_str());
        if (res != 0) {
            std::cerr << "[-] Failed to clone remote repository.\n";
            return 1;
        }
        repo_dir = temp_dir;
        std::cout << "[+] Clone successfully completed.\n";
    }

    if (mode.empty()) {
        std::cout << "============================================================\n";
        std::cout << " BaekjoonHub Migration Tool (C++ High-Performance Version) \n";
        std::cout << "============================================================\n";
        std::cout << "Select target migration layout:\n";
        std::cout << "  1. Platform-first (e.g. 백준/Bronze/..., 프로그래머스/lv1/...)\n";
        std::cout << "  2. Language-first (e.g. Python3/백준/..., Java/프로그래머스/...)\n";
        std::cout << "============================================================\n";
        std::cout << "Enter choice (1-2): ";
        std::string choice;
        std::getline(std::cin, choice);
        choice = trim(choice);
        if (choice == "2") mode = "language_first";
        else mode = "platform_first";
    }

    if (dry_run) {
        preview_migration(repo_dir, mode);
    } else {
        preview_migration(repo_dir, mode);
        std::cout << "Do you want to proceed with rewriting Git history? (y/N): ";
        std::string confirm;
        std::getline(std::cin, confirm);
        if (trim(to_lower(confirm)) == "y") {
            execute_rewrite(repo_dir, mode);

            if (is_remote) {
                std::cout << "\n============================================================\n";
                std::cout << " REMOTE PUSH CONFIRMATION\n";
                std::cout << "============================================================\n";
                std::cout << "WARNING: Force pushing will overwrite the remote repository history.\n";
                std::cout << "Do you want to force push the changes to remote? (y/N): ";
                std::string push_confirm;
                std::getline(std::cin, push_confirm);
                if (trim(to_lower(push_confirm)) == "y") {
                    std::string current_branch = trim(run_git_command(repo_dir, {"rev-parse", "--abbrev-ref", "HEAD"}));
                    std::cout << "[+] Force pushing rewritten branch '" << current_branch << "' to origin...\n";
                    run_git_command(repo_dir, {"push", "-f", "origin", current_branch});
                    std::cout << "[+] Push completed successfully!\n";
                } else {
                    std::cout << "[-] Force push cancelled. Migrated repository remains in temporary directory:\n";
                    std::cout << "    " << repo_dir << "\n";
                }
            }
        } else {
            std::cout << "[-] Operation cancelled by user.\n";
        }
    }

    if (!temp_dir.empty()) {
        std::cout << "[+] Cleaning up temporary directory...\n";
        fs::remove_all(temp_dir);
    }

    return 0;
}
