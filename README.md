# hpc05
🖥 Client package for local TU Delft cluster

Script that connects to PBS cluster with headnode. Since `ipyparallel` doesn't cull enginges when inactive and people are lazy (because they forget to `qdel` their jobs), it automatically kills the `ipengines` after two hours of inactivity.