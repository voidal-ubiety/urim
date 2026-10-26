/* rss-exec: run a command and report its own peak RSS, for scripts/hostile.py.
 *
 * Linux ru_maxrss survives exec: a child forked from the (large) Python harness reports at
 * least the harness's RSS. This tiny process forks the real command, so the command's
 * ru_maxrss starts from this helper's ~1 MiB instead.
 * Usage: rss-exec <fd> <command> [args...]. Writes "<KiB>\n" to <fd>, then exits
 * with the command's exit status (or re-raises its terminating signal). The command gets
 * PR_SET_PDEATHSIG(SIGKILL) so killing this helper kills it too: no orphaned hangs.
 */
#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc < 3) return 2;
  int fd = atoi(argv[1]);
  pid_t pid = fork();
  if (pid < 0) return 2;
  if (pid == 0) {
    prctl(PR_SET_PDEATHSIG, SIGKILL);
    close(fd);
    execvp(argv[2], argv + 2);
    _exit(127);
  }
  int status;
  struct rusage usage;
  if (wait4(pid, &status, 0, &usage) < 0) return 2;
  dprintf(fd, "%ld\n", usage.ru_maxrss);
  if (WIFSIGNALED(status)) {
    signal(WTERMSIG(status), SIG_DFL);
    raise(WTERMSIG(status));
  }
  return WIFEXITED(status) ? WEXITSTATUS(status) : 2;
}
