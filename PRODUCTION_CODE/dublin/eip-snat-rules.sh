#!/bin/bash
# EIP SNAT + Policy Routing for Multi-ENI Setup
# Updated: 2026-04-09
#
# ens5 (primary): 172.31.17.239 → 52.16.14.220 (Remote Control + nginx)
# ens6 (ENI-2):   kele1, kana, leni
# ens7 (ENI-3):   shax, pretty88, lont
# ens8 (ENI-4):   daniellek, pile, hele

# --- Flush existing SNAT + mangle rules (idempotent) ---
iptables -t nat -S POSTROUTING | grep 'SNAT' | while read rule; do
  iptables -t nat $(echo "$rule" | sed 's/^-A/-D/')
done
iptables -t mangle -S PREROUTING | grep 'MARK' | while read rule; do
  iptables -t mangle $(echo "$rule" | sed 's/^-A/-D/')
done

# --- Mangle: mark packets by container → ENI ---
# ens6 (mark 100)
iptables -t mangle -A PREROUTING -s 172.18.0.2 -j MARK --set-mark 100
iptables -t mangle -A PREROUTING -s 172.18.0.3 -j MARK --set-mark 100
iptables -t mangle -A PREROUTING -s 172.18.0.4 -j MARK --set-mark 100
# ens7 (mark 200)
iptables -t mangle -A PREROUTING -s 172.18.0.5 -j MARK --set-mark 200
iptables -t mangle -A PREROUTING -s 172.18.0.6 -j MARK --set-mark 200
iptables -t mangle -A PREROUTING -s 172.18.0.7 -j MARK --set-mark 200
# ens8 (mark 300)
iptables -t mangle -A PREROUTING -s 172.18.0.8 -j MARK --set-mark 300
iptables -t mangle -A PREROUTING -s 172.18.0.9 -j MARK --set-mark 300
iptables -t mangle -A PREROUTING -s 172.18.0.10 -j MARK --set-mark 300

# --- Policy routing ---
ip rule del fwmark 100 lookup 101 2>/dev/null; ip rule add fwmark 100 lookup 101 prio 100
ip rule del fwmark 200 lookup 102 2>/dev/null; ip rule add fwmark 200 lookup 102 prio 200
ip rule del fwmark 300 lookup 103 2>/dev/null; ip rule add fwmark 300 lookup 103 prio 300

# --- Route tables ---
ip route replace default via 172.31.16.1 dev ens6 table 101
ip route replace 172.31.16.0/20 dev ens6 scope link table 101
ip route replace default via 172.31.16.1 dev ens7 table 102
ip route replace 172.31.16.0/20 dev ens7 scope link table 102
ip route replace default via 172.31.16.1 dev ens8 table 103
ip route replace 172.31.16.0/20 dev ens8 scope link table 103

# --- SNAT rules ---
# ens6
iptables -t nat -I POSTROUTING -s 172.18.0.2 -o ens6 -j SNAT --to-source 172.31.30.123
iptables -t nat -I POSTROUTING -s 172.18.0.3 -o ens6 -j SNAT --to-source 172.31.22.196
iptables -t nat -I POSTROUTING -s 172.18.0.4 -o ens6 -j SNAT --to-source 172.31.30.240
# ens7
iptables -t nat -I POSTROUTING -s 172.18.0.5 -o ens7 -j SNAT --to-source 172.31.31.124
iptables -t nat -I POSTROUTING -s 172.18.0.6 -o ens7 -j SNAT --to-source 172.31.19.230
iptables -t nat -I POSTROUTING -s 172.18.0.7 -o ens7 -j SNAT --to-source 172.31.19.243
# ens8
iptables -t nat -I POSTROUTING -s 172.18.0.8 -o ens8 -j SNAT --to-source 172.31.26.213
iptables -t nat -I POSTROUTING -s 172.18.0.9 -o ens8 -j SNAT --to-source 172.31.22.165
iptables -t nat -I POSTROUTING -s 172.18.0.10 -o ens8 -j SNAT --to-source 172.31.29.244

echo "EIP SNAT + policy routing applied at $(date)"
