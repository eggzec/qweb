# Sun N1 / Oracle Grid Engine (SGE) Commands Reference

## Overview

Essential **SGE (Sun Grid Engine)** commands used to **submit, monitor, control, and manage** jobs and queues in a compute cluster. This comprehensive guide is based on the Oracle Sun N1 Grid Engine 6.1 User's Guide.

---

## Table of Contents

1. [User Categories and Permissions](#1-user-categories-and-permissions)
2. [QMON Graphical Interface](#2-qmon-graphical-interface)
3. [Submitting Jobs](#3-submitting-jobs)
4. [Monitoring Jobs and Queues](#4-monitoring-jobs-and-queues)
5. [Controlling Jobs](#5-controlling-jobs)
6. [Queue Management](#6-queue-management)
7. [Host Information](#7-host-information)
8. [Resource Attributes](#8-resource-attributes-and-requirements)
9. [Checkpointing Jobs](#9-checkpointing-jobs)
10. [Configuration Commands](#10-configuration-commands)
11. [Accounting and Reporting](#11-accounting-and-reporting)

---

## 1. User Categories and Permissions

### User Categories

The grid engine system has four user categories with different privileges:

| Category    | Capabilities                                                                 |
| ----------- | ---------------------------------------------------------------------------- |
| **Manager** | Full administrative capabilities; can manipulate all aspects of the system   |
| **Operator** | Many manager commands except configuration changes (adding/modifying queues) |
| **Owner**   | Can suspend/enable owned queues and jobs within those queues                 |
| **User**    | Can submit, monitor, and control their own jobs only                         |

**Note**: Superusers on administration hosts are managers by default.

### Command Capabilities by User Category

| Command   | Manager | Operator | Owner           | User            |
| --------- | ------- | -------- | --------------- | --------------- |
| `qacct`   | Full    | Full     | Own jobs only   | Own jobs only   |
| `qalter`  | Full    | Full     | Own jobs only   | Own jobs only   |
| `qconf`   | Full    | No setup | Show only       | Show only       |
| `qdel`    | Full    | Full     | Own jobs only   | Own jobs only   |
| `qhold`   | Full    | Full     | Own jobs only   | Own jobs only   |
| `qmod`    | Full    | Full     | Own jobs/queues | Own jobs only   |
| `qmon`    | Full    | No setup | No config       | No config       |
| `qstat`   | Full    | Full     | Full            | Full            |
| `qsub`    | Full    | Full     | Full            | Full            |

### Viewing Managers and Operators

```bash
qconf -sm              # Display list of managers
qconf -so              # Display list of operators
```

### Access Control Lists (ACLs)

ACLs control access to queues and parallel environments:

```bash
qconf -sul                    # List all configured ACLs
qconf -su acl-name            # Show entries in specific ACL
```

ACL entries include:
- User account names
- UNIX group names (prefixed with `@`)

### Queue Access Permissions

Queues use two parameters for access control:
- **user_lists**: Users/groups allowed to access the queue
- **xuser_lists**: Users/groups denied access to the queue
- If both are empty, all valid users can access the queue

### Project Access

```bash
qconf -sprjl                  # List all defined projects
qconf -sprj project-name      # Show project configuration
qsub -P project-name job.sh   # Submit job to specific project
```

---

## 2. QMON Graphical Interface

### Launching QMON

```bash
qmon
```

The QMON Main Control window provides graphical access to most SGE functions.

### QMON Customization

Configuration files (in precedence order):
1. User's home directory: `$HOME/.qmon_preferences`
2. Private resource files: `$HOME/.Xdefaults` or `$HOME/.Xresources`
3. Site-specific: `/usr/lib/X11/app-defaults/Qmon`
4. Default: `$SGE_ROOT/qmon/Qmon`

Save customizations using the **Save** button in Job Customize or Queue Customize dialog boxes.

---

## 3. Submitting Jobs

### **qsub**

Submit a job script to the cluster.

```bash
qsub [options] script.sh
```

### Common Options

| Option                | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `-N name`             | Set job name                                            |
| `-cwd`                | Run job in the current working directory                |
| `-o file`             | Redirect standard output                                |
| `-e file`             | Redirect standard error                                 |
| `-j y`                | Merge stdout and stderr                                 |
| `-pe pe_name n`       | Request parallel environment (n slots)                  |
| `-l resource=value`   | Request resource (e.g., mem_free=4G, s_cpu=0:5:0)       |
| `-t 1-100`            | Submit an array job (100 sub-tasks)                     |
| `-M user@example.com` | Send job status notifications                           |
| `-m beas`             | When to send email (b=begin, e=end, a=abort, s=suspend) |
| `-hold_jid jobid`     | Hold current job until another finishes                 |
| `-P project-name`     | Submit job to specific project                          |
| `-q queue-name`       | Request specific queue                                  |
| `-ckpt ckpt_name`     | Specify checkpointing environment                       |
| `-c occasion`         | Define checkpoint occasions                             |
| `-b y`                | Treat command as binary (not script)                    |

### Example Job Script

```bash
#!/bin/bash
#$ -pe mpi 6
#$ -j y
#$ -cwd
#$ -N TESTQSUB
#$ -q all.q

date
./run_analysis.sh
```

### Submission Examples

```bash
qsub job_script.sh
qsub -N myjob -cwd -o output.txt -e error.txt script.sh
qsub -b y sleep 60                    # Submit binary directly
qsub -l s_cpu=0:5:0 script.sh         # Request 5 min CPU time
qsub -l mem_free=4G script.sh         # Request 4GB memory
qsub -P myproject script.sh           # Submit to project
```

---

## 4. Monitoring Jobs and Queues

### **qstat**

Display job and queue status.

```bash
qstat                  # Overview of submitted jobs only
qstat -f               # Full queue and job information
qstat -ext             # Extended info (CPU, memory, tickets)
```

### Common Options

| Option        | Description                                    |
| ------------- | ---------------------------------------------- |
| `-f`          | Full queue and job information                 |
| `-ext`        | Extended job info (CPU, memory, tickets, etc.) |
| `-r`          | Show resource requirements for jobs            |
| `-u username` | Show jobs for a specific user                  |
| `-u '*'`      | Show all users' jobs                           |
| `-j job-id`   | Detailed information for a specific job        |
| `-s r`        | Show only running jobs                         |
| `-s p`        | Show only pending jobs                         |
| `-s z`        | Show recently finished jobs                    |
| `-t`          | Show which nodes parallel jobs run on          |
| `-l resource` | Filter by resource requirement                 |

### Job States

| Code  | Meaning                          |
| ----- | -------------------------------- |
| `r`   | Running                          |
| `s`   | Suspended                        |
| `q`   | Queued                           |
| `w`   | Waiting                          |
| `t`   | Transferring                     |
| `qw`  | Queued and waiting               |
| `E`   | Error                            |
| `R`   | Restarted (migrating checkpoint) |
| `dr`  | Deleted but running              |
| `hqw` | Held and waiting                 |
| `hRr` | Held and running                 |

### Queue States

| Code | Meaning                        |
| ---- | ------------------------------ |
| `a`  | Load threshold alarm           |
| `o`  | Orphaned                       |
| `A`  | Suspend threshold alarm        |
| `C`  | Suspended by calendar          |
| `D`  | Disabled by calendar           |
| `c`  | Configuration ambiguous        |
| `d`  | Disabled                       |
| `s`  | Suspended                      |
| `S`  | Suspended by subordination     |
| `u`  | Unknown                        |
| `E`  | Error                          |
| `au` | Alarm, unreachable             |

### qstat Output Examples

**Basic qstat output:**

```
job-ID  prior  name      user     state  submit/start at      queue    function
231     0      hydra     craig    r      07/13/96 20:27:15   durin.q  MASTER
232     0      compile   penny    r      07/13/96 20:30:40   durin.q  MASTER
230     0      blackhole don      r      07/13/96 20:26:10   dwain.q  MASTER
233     0      mac       elaine   r      07/13/96 20:30:40   dwain.q  MASTER
234     0      golf      shannon  r      07/13/96 20:31:44   dwain.q  MASTER
236     5      word      elaine   qw     07/13/96 20:32:07
235     0      andrun    penny    qw     07/13/96 20:31:43
```

**qstat -f output:**

```
queuename          qtype  used/free  load_avg  arch    states

dq                 BIP    0/1        99.99     sun4    au

durin.q            BIP    2/2        0.36      sun4
  231  0  hydra     craig    r  07/13/96 20:27:15  MASTER
  232  0  compile   penny    r  07/13/96 20:30:40  MASTER

dwain.q            BIP    3/3        0.36      sun4
  230  0  blackhole don      r  07/13/96 20:26:10  MASTER
  233  0  mac       elaine   r  07/13/96 20:30:40  MASTER
  234  0  golf      shannon  r  07/13/96 20:31:44  MASTER

fq                 BIP    0/3        0.36      sun4

################################################################################
- PENDING JOBS - PENDING JOBS - PENDING JOBS - PENDING JOBS - PENDING JOBS -
################################################################################
  236  5  word      elaine   qw  07/13/96 20:32:07
  235  0  andrun    penny    qw  07/13/96 20:31:43
```

### Queue Description Columns

- **qtype**: Queue type (B=batch, I=interactive, P=parallel)
- **used/free**: Count of used and free job slots
- **load_avg**: Load average of the queue
- **arch**: Architecture
- **states**: Current queue state(s)

### qstat -ext Columns

- **cpu/mem/io**: Currently accumulated CPU, memory, and I/O usage
- **tckts**: Total number of tickets assigned to the job
- **ovrts**: Override tickets assigned through `qalter -ot`
- **otckt**: Tickets assigned through the override policy
- **ftckt**: Tickets assigned through the functional policy
- **stckt**: Tickets assigned through the share-based policy
- **deadline**: Deadline initiation time (if applicable)
- **share**: Current resource share relative to all cluster jobs

### Common qstat Commands

```bash
qstat                          # Show all your jobs
qstat -f                       # Full queue and job information
qstat -u '*'                   # Show all users' jobs
qstat -u username              # Show specific user's jobs
qstat -s z -u '*'              # View recently completed jobs
qstat -j 1234                  # Detailed info for job 1234
qstat -t                       # See nodes for parallel jobs
qstat -r                       # Show resource requirements
qstat -ext                     # Extended usage and ticket info
qstat -l arch=linux            # Filter by resource requirement
```

### Troubleshooting Pending Jobs

```bash
qstat -j job-id                # Get detailed job information
```

The output includes scheduling information explaining why the job hasn't been dispatched.

**Note**: The scheduler must have `schedd_job_info` set to `true` for meaningful scheduling information.

### qstat Configuration Files

- **Cluster-wide**: `$SGE_ROOT/$SGE_CELL/common/sge_qstat`
- **User private**: `$HOME/.sge_qstat`

The home directory file has highest precedence. Command line options override file settings.

---

## 5. Controlling Jobs

### **qdel**

Delete (cancel) jobs.

```bash
qdel job-id
qdel job-id1,job-id2           # Delete multiple jobs
qdel -f job-id                 # Force delete
```

**Permission Requirements**: You must be the job owner, a grid engine manager, or an operator.

**Force Delete**: The `-f` option registers the status change at `sge_qmaster` without contacting `sge_execd`. Use when `sge_execd` is unreachable (e.g., network problems). Intended for administrators only, but users can force-delete their own jobs if `ENABLE_FORCED_QDEL` flag is set in cluster configuration.

### **qmod**

Modify job or queue states.

#### Job Control

| Command                        | Description                  |
| ------------------------------ | ---------------------------- |
| `qmod -s job-id`               | Suspend a job                |
| `qmod -us job-id`              | Unsuspend (resume) a job     |
| `qmod -s job-id.task-id-range` | Suspend array job tasks      |
| `qmod -us -f job-id1,job-id2`  | Force resume multiple jobs   |
| `qmod -c job-id`               | Clear an error state         |

#### Queue Control

| Command              | Description              |
| -------------------- | ------------------------ |
| `qmod -d queue-name` | Disable a queue          |
| `qmod -e queue-name` | Enable a queue           |
| `qmod -s queue-name` | Suspend a queue          |
| `qmod -us queue-name`| Unsuspend a queue        |
| `qmod -d *@node`     | Disable node in all queues |
| `qmod -e *@node`     | Enable node in all queues  |

**Permission Requirements**: To delete, suspend, or resume a job, you must be the job owner, a manager, or an operator.

**Force Option**: The `-f` option registers changes at `sge_qmaster` without contacting `sge_execd`. Use when the execution host is unreachable.

### Job Suspension

- Sends `SIGSTOP` signal to the process group
- Job stops consuming CPU time
- Resumption sends `SIGCONT` signal

### Examples

```bash
qdel 2345                      # Delete job 2345
qdel -f 2345                   # Force delete job 2345
qdel 2345,2346                 # Delete multiple jobs
qmod -s 2345                   # Suspend job 2345
qmod -us 2345                  # Resume job 2345
qmod -s 1234.5-10              # Suspend array job tasks 5-10
qmod -d all.q                  # Disable all.q queue
qmod -e all.q                  # Enable all.q queue
qmod -d all.q@compute-01       # Disable specific queue instance
```

### **qalter**

Modify parameters of a submitted job.

```bash
qalter [options] job-id
qalter -p 10 job-id            # Change priority
```

### **qhold** / **qrls**

Block or release pending jobs.

```bash
qhold job-id                   # Put job on hold
qrls job-id                    # Release held job
```

Hold types:
- **User holds**: Can be set/reset by job owner, managers, and operators
- **Operator holds**: Can be set/reset by managers and operators
- **System holds**: Can be set/reset by managers only

### **qresub**

Duplicate a job.

```bash
qresub job-id
```

---

## 6. Queue Management

### Displaying Queues

```bash
qconf -sql                     # List all configured queues
qconf -sq queue-name           # Show queue configuration
qstat -f                       # View queue states and jobs
```

### Important Queue Parameters

| Parameter        | Description                                              |
| ---------------- | -------------------------------------------------------- |
| `qname`          | Queue name                                               |
| `qtype`          | Queue type (B=batch, I=interactive, P=parallel)          |
| `slots`          | Number of concurrent jobs allowed                        |
| `hostlist`       | Hosts/host groups associated with queue                  |
| `processors`     | Processors available to queue (multiprocessor systems)   |
| `owner_list`     | Queue owners                                             |
| `user_lists`     | ACLs of users allowed access                             |
| `xuser_lists`    | ACLs of users denied access                              |
| `project_lists`  | Projects allowed access                                  |
| `xproject_lists` | Projects denied access                                   |
| `complex_values` | Resource capacities for queue                            |

### Queue Control Commands

```bash
qmod -d queue-name             # Disable queue
qmod -e queue-name             # Enable queue
qmod -s queue-name             # Suspend queue
qmod -us queue-name            # Unsuspend queue
qmod -d queue@node             # Disable specific queue instance
qmod -e queue@node             # Enable specific queue instance
qmod -d *@node                 # Disable node in all queues
qmod -e *@node                 # Enable node in all queues
```

### Suspended vs Disabled Queues

**Suspended queues**:
- Closed for new jobs
- Running jobs are also suspended
- Jobs unsuspend when queue is resumed
- Note: Explicitly suspended jobs must be resumed explicitly

**Disabled queues**:
- Closed for new jobs
- Running jobs continue to execute
- Commonly used to clear a queue

---

## 7. Host Information

### Master Host

Find the current master host:

```bash
cat $SGE_ROOT/$SGE_CELL/common/act_qmaster
```

**Note**: The master host location can migrate between master and shadow master hosts.

### **qhost**

Display hosts with load information.

```bash
qhost                          # Show all execution hosts
```

### Execution Hosts

```bash
qconf -sel                     # List all execution hosts
qconf -se hostname             # Show execution host details
qhost                          # Show host status and load
```

### Administration Hosts

```bash
qconf -sh                      # List administration hosts
```

### Submit Hosts

```bash
qconf -ss                      # List submit hosts
```

---

## 8. Resource Attributes and Requirements

### Complex Resource Attributes

Display all configured resource attributes:

```bash
qconf -sc                      # Show complex configuration
```

### Example Complex Attributes Output

```
#name            shortcut  type     relop  requestable  consumable  default  urgency
#-----------------------------------------------------------------------------------
arch             a         RESTRING ==     YES          NO          NONE     0
calendar         c         STRING   ==     YES          NO          NONE     0
cpu              cpu       DOUBLE   >=     YES          NO          0        0
h_core           h_core    MEMORY   <=     YES          NO          0        0
h_cpu            h_cpu     TIME     <=     YES          NO          0:0:0    0
h_data           h_data    MEMORY   <=     YES          NO          0        0
h_fsize          h_fsize   MEMORY   <=     YES          NO          0        0
h_rss            h_rss     MEMORY   <=     YES          NO          0        0
h_rt             h_rt      TIME     <=     YES          NO          0:0:0    0
h_stack          h_stack   MEMORY   <=     YES          NO          0        0
h_vmem           h_vmem    MEMORY   <=     YES          NO          0        0
hostname         h         HOST     ==     YES          NO          NONE     0
load_avg         la        DOUBLE   >=     NO           NO          0        0
mem_free         mf        MEMORY   <=     YES          NO          0        0
mem_total        mt        MEMORY   <=     YES          NO          0        0
mem_used         mu        MEMORY   >=     YES          NO          0        0
num_proc         p         INT      ==     YES          NO          0        0
qname            q         STRING   ==     YES          NO          NONE     0
s_core           s_core    MEMORY   <=     YES          NO          0        0
s_cpu            s_cpu     TIME     <=     YES          NO          0:0:0    0
s_data           s_data    MEMORY   <=     YES          NO          0        0
s_fsize          s_fsize   MEMORY   <=     YES          NO          0        0
s_rss            s_rss     MEMORY   <=     YES          NO          0        0
s_rt             s_rt      TIME     <=     YES          NO          0:0:0    0
s_stack          s_stack   MEMORY   <=     YES          NO          0        0
s_vmem           s_vmem    MEMORY   <=     YES          NO          0        0
slots            s         INT      <=     YES          YES         1        1000
swap_free        sf        MEMORY   <=     YES          NO          0        0
swap_total       st        MEMORY   <=     YES          NO          0        0
tmpdir           tmp       STRING   ==     NO           NO          NONE     0
virtual_free     vf        MEMORY   <=     YES          NO          0        0
virtual_total    vt        MEMORY   <=     YES          NO          0        0
```

### Column Descriptions

- **name**: Full attribute name
- **shortcut**: Abbreviation for use in qsub commands
- **type**: Data type (MEMORY, TIME, INT, STRING, etc.)
- **relop**: Relational operator used for comparison (==, <=, >=)
- **requestable**: Whether users can request this attribute
- **consumable**: Whether this is a consumable resource
- **default**: Default value
- **urgency**: Urgency weight for scheduling

### Requesting Resources

Use the `-l` option with `qsub`:

```bash
qsub -l resource=value job.sh
qsub -l shortcut=value job.sh
```

The comparison executed is:
```
User_Request [relop] Queue/Host/Property
```

If the comparison is false, the job cannot run in that queue or on that host.

### Resource Request Examples

```bash
# Request 5 minutes soft CPU time limit
qsub -l s_cpu=0:5:0 script.sh

# Request specific architecture
qsub -l arch=solaris64 script.sh

# Request memory
qsub -l mem_free=4G script.sh

# Request virtual memory
qsub -l s_vmem=2G script.sh

# Multiple resource requests
qsub -l arch=linux,mem_free=4G,s_cpu=0:30:0 script.sh

# Request specific host (if requestable)
qsub -l hostname=compute-01 script.sh

# Request specific queue (if requestable)
qsub -l qname=all.q script.sh

# Use shortcuts
qsub -l a=linux,mf=4G script.sh
```

**Note**: Administrators can make certain attributes unrequestable (e.g., `hostname`, `qname`) to enforce load balancing.

---

## 9. Checkpointing Jobs

### Types of Checkpointing

1. **User-Level Checkpointing**: Application-integrated restart mechanisms or checkpointing libraries
2. **Kernel-Level Checkpointing**: OS-level checkpointing of processes or process hierarchies

### Submitting Checkpointing Jobs

```bash
qsub -ckpt ckpt_env_name script.sh
qsub -ckpt ckpt_env -c s script.sh     # Checkpoint on shutdown
```

### Checkpoint Occasions (`-c` option)

| Value      | Description                                      |
| ---------- | ------------------------------------------------ |
| `n`        | No checkpoint (highest precedence)               |
| `s`        | Checkpoint when `sge_execd` is shut down         |
| `m`        | Checkpoint at minimum CPU interval               |
| `x`        | Checkpoint when job is suspended                 |
| `hh:mm:ss` | Checkpoint at specified interval (e.g., 01:00:00)|

### Checkpointing Job Script Example

```bash
#!/bin/sh
#Force /bin/sh in Grid Engine
#$ -S /bin/sh

# Test if restarted/migrated
if [ $RESTARTED = 0 ]; then
    # 0 = not restarted
    # Parts to be executed only during first start
    set_up_grid
fi

# Start the checkpointing executable
fem
#End of scriptfile
```

### Job Migration

Checkpointing jobs are stopped and migrated when:
- The executing queue or job is suspended explicitly (`qmod`)
- The job or queue is suspended automatically (suspend threshold exceeded) and the checkpoint occasion includes suspension case

When migrated, the job:
- Moves back to `sge_qmaster`
- Shows status `R` (restarted) in `qstat` output
- Is dispatched to another suitable queue if available

### File System Requirements

- Sufficient disk space for checkpoint files
- Checkpoint files must be visible on all machines (NFS or similar required)
- Checkpoint directory specified by `ckpt_dir` parameter in checkpoint environment
- If `ckpt_dir=NONE`, uses job's starting directory (use `qsub -cwd`)

---

## 10. Configuration Commands

### **qconf**

Administrative configuration tool.

#### Queue Configuration

| Command                | Description                   |
| ---------------------- | ----------------------------- |
| `qconf -sql`           | Show queue list               |
| `qconf -sq queue_name` | Show queue configuration      |
| `qconf -mq queue_name` | Modify queue (managers)       |
| `qconf -aq`            | Add queue (managers)          |
| `qconf -dq queue_name` | Delete queue (managers)       |

#### Host Configuration

| Command                | Description                   |
| ---------------------- | ----------------------------- |
| `qconf -sel`           | Show execution host list      |
| `qconf -se hostname`   | Show host configuration       |
| `qconf -me hostname`   | Modify host (managers)        |
| `qconf -ae`            | Add execution host (managers) |
| `qconf -de hostname`   | Delete host (managers)        |
| `qconf -sh`            | Show administration hosts     |
| `qconf -ss`            | Show submit hosts             |

#### Complex Configuration

| Command     | Description                      |
| ----------- | -------------------------------- |
| `qconf -sc` | Show complex resource attributes |
| `qconf -mc` | Modify complex (managers)        |

#### Scheduler Configuration

| Command         | Description                   |
| --------------- | ----------------------------- |
| `qconf -sconf`  | Show scheduler configuration  |
| `qconf -msconf` | Modify scheduler (managers)   |

#### Parallel Environment

| Command             | Description                      |
| ------------------- | -------------------------------- |
| `qconf -spl`        | Show parallel environment list   |
| `qconf -sp pe_name` | Show PE configuration            |
| `qconf -mp pe_name` | Modify PE (managers)             |
| `qconf -ap`         | Add PE (managers)                |
| `qconf -dp pe_name` | Delete PE (managers)             |

#### User Management

| Command              | Description          |
| -------------------- | -------------------- |
| `qconf -sm`          | Show managers        |
| `qconf -am username` | Add manager          |
| `qconf -dm username` | Delete manager       |
| `qconf -so`          | Show operators       |
| `qconf -ao username` | Add operator         |
| `qconf -do username` | Delete operator      |

#### ACL Management

| Command              | Description          |
| -------------------- | -------------------- |
| `qconf -sul`         | Show user ACL list   |
| `qconf -su acl-name` | Show user ACL        |
| `qconf -mu acl-name` | Modify ACL (managers)|
| `qconf -au acl-name` | Add ACL (managers)   |
| `qconf -du acl-name` | Delete ACL (managers)|

#### Project Management

| Command                    | Description               |
| -------------------------- | ------------------------- |
| `qconf -sprjl`             | Show project list         |
| `qconf -sprj project-name` | Show project config       |
| `qconf -mprj project-name` | Modify project (managers) |
| `qconf -aprj`              | Add project (managers)    |
| `qconf -dprj project-name` | Delete project (managers) |

---

## 11. Accounting and Reporting

### **qacct**

Show accounting data for finished jobs.

```bash
qacct -j job-id                # Job accounting info
qacct -o username              # Accounting for user
qacct -help                    # Show help
```

---

## 12. Email Notifications

Configure email notifications using the `-m` option with `qsub`:

| Flag | Description                            |
| ---- | -------------------------------------- |
| `b`  | Send email at beginning of job         |
| `e`  | Send email at end of job               |
| `a`  | Send email when job is aborted         |
| `s`  | Send email when job is suspended       |
| `n`  | Do not send email (default)            |

### Examples

```bash
qsub -m be -M user@example.com script.sh    # Email at begin and end
qsub -m a -M admin@example.com script.sh    # Email on abort
qsub -m beas -M user@example.com script.sh  # Email on all events
```

---

## 13. Interactive Jobs

### **qsh**

Submit interactive job in graphical mode.

```bash
qsh [options]
```

### **qlogin**

Open interactive text-mode session.

```bash
qlogin [options]
qlogin -l mem_free=4G          # Request resources
```

---

## 14. Job Selection

### **qselect**

Display queues based on criteria.

```bash
qselect [options]
qselect -l arch=linux          # Select Linux queues
qselect -q '*@host*'           # Select queues on host
```

---

## 15. Example Workflows

### Basic Job Workflow

```bash
# Submit a job
qsub -N myjob -cwd run.sh

# Check all jobs
qstat -u '*'

# Get detailed job info
qstat -j 1023

# Suspend the job
qmod -s 1023

# Resume the job
qmod -us 1023

# Delete a job
qdel 1023

# Check accounting for completed job
qacct -j 1023
```

### Array Job Workflow

```bash
# Submit array job
qsub -t 1-100 -N array_job script.sh

# Check array job status
qstat -t

# Suspend specific tasks
qmod -s 1234.5-10

# Delete specific tasks
qdel 1234.5-10
```

### Parallel Job Workflow

```bash
# Submit MPI job requesting 16 slots
qsub -pe mpi 16 -N parallel_job mpi_script.sh

# Check where parallel job is running
qstat -t

# Check detailed parallel job info
qstat -j 1234
```

### Resource Request Workflow

```bash
# Submit job with resource requirements
qsub -l s_cpu=0:5:0,mem_free=4G,arch=linux script.sh

# Check resource requirements
qstat -r

# Filter queues by resource
qstat -l arch=linux
```

### Queue Management Workflow

```bash
# Check queue status
qstat -f

# Disable a queue
qmod -d all.q@compute-01

# Enable a queue
qmod -e all.q@compute-01

# Disable node in all queues
qmod -d '*@compute-01'

# View queue configuration
qconf -sq all.q
```

### Checkpointing Job Workflow

```bash
# Submit checkpointing job
qsub -ckpt my_ckpt_env -c x script.sh

# Monitor checkpointing job
qstat -j 1234

# Job will migrate when suspended
qmod -s 1234

# Check if job restarted (status R)
qstat
```

---

## 16. Useful Command Combinations

### View All Jobs

```bash
qstat -u \*                    # View all jobs (escaped asterisk)
qstat -u '*'                   # View all jobs (quoted asterisk)
```

### View Recently Completed Jobs

```bash
qstat -s z -u '*'              # Recently finished jobs
```

### Submit Binary Command

```bash
qsub -b y sleep 60             # Submit binary directly
qsub -b y ./my_executable      # Submit executable
```

### Check Parallel Job Node Distribution

```bash
qstat -t                       # See which nodes jobs run on
```

### Understand Why Job Doesn't Start

```bash
qstat -j job-id                # Detailed job information
qstat -j job-id | grep scheduling  # Scheduling info
```

### Disable/Enable Nodes

```bash
qmod -d queue@node             # Disable queue on node
qmod -e queue@node             # Enable queue on node
qmod -d \*@node                # Disable node in all queues
qmod -e \*@node                # Enable node in all queues
```

### Check Node Status

```bash
qstat -f                       # Full queue status
qhost                          # Host load information
qconf -se hostname             # Host configuration
```

### List SGE System Variables

```bash
qstat -F                       # List all system variables
```

---

## 17. Important Environment Variables

### Job Environment Variables

| Variable          | Description                              |
| ----------------- | ---------------------------------------- |
| `$JOB_ID`         | Unique job identification number         |
| `$JOB_NAME`       | Name of the job                          |
| `$QUEUE`          | Name of the queue job is running in      |
| `$HOSTNAME`       | Name of the execution host               |
| `$RESTARTED`      | 0 = first start, 1 = restarted           |
| `$SGE_TASK_ID`    | Array job task ID                        |
| `$NSLOTS`         | Number of slots (parallel jobs)          |
| `$PE`             | Parallel environment name                |
| `$SGE_ROOT`       | SGE installation root directory          |
| `$SGE_CELL`       | SGE cell name                            |

---

## 18. Queue Types

### Queue Type Codes

| Code | Type        | Description                              |
| ---- | ----------- | ---------------------------------------- |
| `B`  | Batch       | Batch queue for non-interactive jobs     |
| `I`  | Interactive | Interactive queue for qsh/qlogin         |
| `P`  | Parallel    | Parallel queue for MPI/parallel jobs     |

Queues can be combinations (e.g., `BIP` = batch, interactive, parallel).

---

## 19. Troubleshooting Tips

### Job Won't Start

1. Check job details: `qstat -j job-id`
2. Look for scheduling info explaining why job is pending
3. Verify resource requirements don't exceed available resources
4. Check queue access permissions (user_lists/xuser_lists)
5. Verify project access if using projects
6. Ensure `schedd_job_info` is enabled for detailed info

### Job in Error State

1. Check error details: `qstat -j job-id`
2. View job output files for errors
3. Clear error state after fixing: `qmod -c job-id`
4. Verify file permissions and paths

### Queue Issues

1. Check queue state: `qstat -f`
2. View queue configuration: `qconf -sq queue-name`
3. Check if queue is disabled/suspended
4. Verify host availability: `qhost`

### Force Operations

Use `-f` flag when execution host is unreachable:
```bash
qdel -f job-id                 # Force delete
qmod -us -f job-id             # Force unsuspend
qmod -e -f queue-name          # Force enable
```

---

## 20. Best Practices

### Job Submission

- Always use `-cwd` for jobs that need current directory
- Use `-j y` to merge stdout and stderr for easier debugging
- Specify resource requirements to ensure proper scheduling
- Use meaningful job names with `-N`
- Request appropriate email notifications with `-m`

### Resource Requests

- Request only resources actually needed
- Use soft limits (`s_*`) for resources that can be exceeded
- Use hard limits (`h_*`) for strict resource enforcement
- Be specific with architecture requirements

### Monitoring

- Use `qstat -u '*'` regularly to check cluster load
- Check `qstat -f` for queue availability
- Use `qstat -j job-id` before deleting or modifying jobs
- Monitor recently finished jobs with `qstat -s z -u '*'`

### Queue Management

- Disable queues (not suspend) when clearing for maintenance
- Use suspend for temporary holds on job execution
- Clear error states promptly with `qmod -c`
- Communicate with users before disabling production queues

### Checkpointing

- Use checkpointing for long-running jobs
- Ensure NFS or shared filesystem is available
- Test checkpoint/restart mechanism before production use
- Set appropriate checkpoint intervals

---

## 21. Configuration File Locations

### Important Files and Directories

| Location                                      | Description                    |
| --------------------------------------------- | ------------------------------ |
| `$SGE_ROOT/$SGE_CELL/common/`                 | Common configuration files     |
| `$SGE_ROOT/$SGE_CELL/common/act_qmaster`     | Current master host            |
| `$SGE_ROOT/$SGE_CELL/common/sge_qstat`       | Cluster-wide qstat config      |
| `$HOME/.sge_qstat`                            | User qstat configuration       |
| `$HOME/.qmon_preferences`                     | QMON user preferences          |
| `/usr/lib/X11/app-defaults/Qmon`              | Site-wide QMON resources       |
| `$SGE_ROOT/qmon/Qmon`                         | Default QMON resource file     |

---

## 22. Signal Handling

### Job Control Signals

| Action     | Signal     | Description                        |
| ---------- | ---------- | ---------------------------------- |
| Suspend    | `SIGSTOP`  | Halts job, stops CPU consumption   |
| Resume     | `SIGCONT`  | Continues suspended job            |
| Terminate  | `SIGTERM`  | Graceful termination request       |
| Kill       | `SIGKILL`  | Forceful termination               |

---

## 23. Return Codes and Exit Status

Jobs return exit codes that can be checked with `qacct`:

| Code | Meaning                                |
| ---- | -------------------------------------- |
| 0    | Successful completion                  |
| 1-255| Application-specific error codes       |

Use `qacct -j job-id` to view exit status and failure information.

---

## 24. Advanced Features

### Job Dependencies

```bash
# Hold job until another completes
qsub -hold_jid job-id script.sh

# Multiple dependencies
qsub -hold_jid job-id1,job-id2 script.sh
```

### Job Arrays

```bash
# Submit 100 identical tasks
qsub -t 1-100 script.sh

# Array with step size (2, 4, 6, 8, 10)
qsub -t 2-10:2 script.sh

# Use $SGE_TASK_ID in script
echo "Task $SGE_TASK_ID running"
```

### Priority Management

```bash
# Set job priority (-1023 to 1024)
qsub -p 100 script.sh

# Modify priority of pending job
qalter -p 200 job-id
```

### Calendar-Based Scheduling

Queues can be automatically suspended/disabled by calendar:
- Queue state shows `C` (suspended by calendar)
- Queue state shows `D` (disabled by calendar)

---

## 25. Performance Considerations

### Scheduling Efficiency

- Avoid requesting unrequestable resources
- Request multiple resources together, not separately
- Use queue domains for similar configurations
- Minimize job submission overhead for array jobs

### Load Balancing

- Let scheduler choose queue when possible
- Avoid hard-coding queue names unless necessary
- Use resource requirements instead of queue selection
- Administrator can make hostname/qname unrequestable

### Consumable Resources

- Slots are consumable (limited capacity)
- Memory can be configured as consumable
- System tracks and schedules based on availability
- Use `qstat -ext` to monitor resource consumption

---

## 26. Common Error Messages

### "error: no suitable queues"

**Cause**: No queues match job requirements
**Solution**: 
- Check resource requirements with `qstat -r`
- Verify queue configuration with `qconf -sq`
- Check access permissions (user_lists/xuser_lists)

### "job is in error state"

**Cause**: Job encountered an error during execution
**Solution**:
- Check job details: `qstat -j job-id`
- Review output/error files
- Fix underlying issue
- Clear error: `qmod -c job-id`

### "cannot send message to execd"

**Cause**: Execution daemon unreachable
**Solution**:
- Check network connectivity
- Verify `sge_execd` is running
- Use `-f` flag to force operation if needed

---

## 27. Man Pages Reference

### Essential Man Pages

```bash
man qsub           # Job submission
man qstat          # Job and queue monitoring
man qdel           # Job deletion
man qmod           # Job and queue modification
man qconf          # Configuration management
man qacct          # Accounting information
man qalter         # Job modification
man qhold          # Job hold
man qrls           # Job release
man qhost          # Host information
man qsh            # Interactive graphical jobs
man qlogin         # Interactive text jobs
man qselect        # Queue selection
man qresub         # Job resubmission
```

### Configuration Man Pages

```bash
man queue_conf     # Queue configuration
man host_conf      # Host configuration
man complex        # Complex resource attributes
man sge_pe         # Parallel environment
man checkpoint     # Checkpointing configuration
man sge_conf       # Global configuration
man sge_qstat      # qstat configuration
man sched_conf     # Scheduler configuration
```

---

## 28. Quick Reference Summary

### Most Common Commands

```bash
# Submit jobs
qsub script.sh
qsub -cwd -N jobname script.sh

# Monitor jobs
qstat
qstat -u '*'
qstat -f
qstat -j job-id

# Control jobs
qdel job-id
qmod -s job-id
qmod -us job-id

# Queue info
qconf -sql
qconf -sq queue-name
qstat -f

# Host info
qhost
qconf -sel
qconf -se hostname

# User info
qconf -sm
qconf -so

# Resources
qconf -sc
```

---

## 29. Additional Resources

### Documentation

- Oracle Sun N1 Grid Engine 6.1 User's Guide: [Chapter 4 - Monitoring and Controlling Jobs and Queues](https://docs.oracle.com/cd/E19957-01/820-0699/index.html)
- Oracle Sun N1 Grid Engine 6.1 Administration Guide
- Man pages: `man -k sge` or `man -k grid`

### Community Resources

- [SGE Basic Commands (French)](http://n0tes.fr/2022/08/10/SGE-Commandes-de-base/)
- [SLURM-SGE Cheat Sheet (French)](http://n0tes.fr/2022/11/01/SLURM-SGE-Cheat-Sheet/)

---

## 30. Notes

### Important Considerations

- Always check job status with `qstat -j job-id` before deletion
- Use `-cwd` flag when submitting jobs that depend on current directory
- Checkpointing requires NFS or similar shared filesystem
- Force operations (`-f`) should be used with caution
- Queue owners can only manage their own queues
- Superusers on admin hosts are managers by default
- The master host location can change dynamically

### Security Notes

- Users can only modify their own jobs (unless manager/operator)
- ACLs control access to queues and parallel environments
- Projects provide additional access control layer
- User/operator/manager permissions are hierarchical

---

*Based on Oracle Sun N1 Grid Engine 6.1 User's Guide*  
*© 2010, Oracle Corporation and/or its affiliates*
