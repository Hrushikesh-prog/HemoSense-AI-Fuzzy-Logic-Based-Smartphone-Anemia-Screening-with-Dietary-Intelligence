import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/screening.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';

/// ⑭ History & trends — grade trend chart (levels 0-2, never Hb numbers)
/// and the scan list with the grade and the anemia risk score.
class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(p.historyProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('History & trends')),
      body: Column(
        children: [
          Expanded(
            child: history.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.history_rounded,
                            size: 56, color: Color(0xFFDCCBD1)),
                        const SizedBox(height: 12),
                        const Text('No screenings yet',
                            style: TextStyle(
                                fontSize: 15, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        Text('Your results will appear here.',
                            style: TextStyle(
                                fontSize: 11, color: Colors.grey.shade600)),
                      ],
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
                    children: [
                      // Trend chart
                      if (history.length >= 2)
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(11, 11, 11, 8),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    const Text('Category level over time',
                                        style: TextStyle(
                                            fontWeight: FontWeight.w700,
                                            fontSize: 12)),
                                    Text(
                                        '${history.last.label} → ${history.first.label}',
                                        style: const TextStyle(
                                            fontSize: 10, color: C.muted)),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                SizedBox(
                                  height: 120,
                                  child: _TrendChart(
                                      entries: history.reversed.toList()),
                                ),
                                const Text(
                                    'Normal 0 · Mild 1 · Moderate-to-Severe 2',
                                    style: TextStyle(
                                        fontSize: 9, color: C.muted)),
                              ],
                            ),
                          ),
                        ),
                      const SizedBox(height: 10),
                      const SectionLabel('All scans'),
                      const SizedBox(height: 5),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 11, vertical: 2),
                          child: Column(
                            children: [
                              for (final e in history)
                                MockListRow(
                                  leading: MiniAvatar(
                                    Icons.visibility_outlined,
                                    bg: C.severityBg(e.severityClass),
                                    fg: C.severityColor(e.severityClass),
                                  ),
                                  title: Text(
                                      DateFormat('d MMM yyyy · HH:mm').format(e.time)),
                                  subtitle: Text([
                                    if (e.headline.isNotEmpty) e.headline,
                                    if (e.riskPercent != null)
                                      'Risk score ${e.riskPercent}%',
                                    '${e.confidence} confidence',
                                  ].join(' · ')),
                                  trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      SeverityPill(e.severityClass),
                                      const Icon(Icons.chevron_right_rounded,
                                          size: 14, color: C.muted),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextButton.icon(
                        icon: const Icon(Icons.delete_outline_rounded,
                            size: 15, color: C.severe),
                        label: const Text('Clear history',
                            style: TextStyle(fontSize: 11, color: C.severe)),
                        onPressed: () {
                          showDialog<void>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: const Text('Clear history?'),
                              content: const Text(
                                  'All saved screenings on this device will be deleted.'),
                              actions: [
                                TextButton(
                                    onPressed: () => Navigator.of(ctx).pop(),
                                    child: const Text('Cancel')),
                                FilledButton(
                                    onPressed: () {
                                      ref
                                          .read(p.historyProvider.notifier)
                                          .clear();
                                      Navigator.of(ctx).pop();
                                    },
                                    child: const Text('Delete')),
                              ],
                            ),
                          );
                        },
                      ),
                    ],
                  ),
          ),
          DisclaimerFooter(),
        ],
      ),
    );
  }
}

class _TrendChart extends StatelessWidget {
  final List<HistoryEntry> entries; // oldest first
  const _TrendChart({required this.entries});

  @override
  Widget build(BuildContext context) {
    final spots = [
      for (var i = 0; i < entries.length; i++)
        FlSpot(i.toDouble(), entries[i].severityLevel.toDouble()),
    ];
    return LineChart(
      LineChartData(
        minY: -0.4,
        maxY: 2.4,
        minX: -0.4,
        maxX: (entries.length - 1).toDouble() + 0.4,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: 1,
          getDrawingHorizontalLine: (v) => const FlLine(
              color: Color(0xFFEEE3E7), strokeWidth: 1),
        ),
        borderData: FlBorderData(show: false),
        titlesData: const FlTitlesData(show: false),
        lineTouchData: const LineTouchData(enabled: false),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            barWidth: 2.4,
            color: C.primary,
            dotData: const FlDotData(show: true),
          ),
        ],
      ),
    );
  }
}
