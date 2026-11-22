/** Builders for tests of the processing: the graph of the pipeline, a node's state, an entry of
 * the log, as the API sends them. */
import type { components } from '#lib/api/schema.ts';
import type { GraphNode } from '#lib/pipeline.ts';

type Node = components['schemas']['Node'];
type NodeState = components['schemas']['NodeStateOut'];
type LogEntry = components['schemas']['LogEntry'];

/** The graph of a pipeline from what each node requires, in the order given. */
export function graphOf(requires: Partial<Record<Node, Node[]>>): GraphNode[] {
	return Object.entries(requires).map(([node, before]) => ({
		node: node as Node,
		requires: before ?? [],
		waits_for: []
	}));
}

/** The state of a node: done (`ok`) from 08:49:01 to 08:49:05, without times while it waits. */
export function nodeState(
	node: Node,
	outcome: NodeState['outcome'] = 'ok',
	status: NodeState['status'] = 'done',
	extra: Partial<NodeState> = {}
): NodeState {
	return {
		node,
		status,
		outcome,
		started_at: status === 'waiting' ? null : '2026-10-14T08:49:01Z',
		finished_at: status === 'done' ? '2026-10-14T08:49:05Z' : null,
		...extra
	};
}

/** An entry of the log: the node ran `ok` in `run` for a second, without input or output. */
export function logEntry(node: Node, run = 1, extra: Partial<LogEntry> = {}): LogEntry {
	return {
		node,
		run,
		outcome: 'ok',
		reason: null,
		confidence: null,
		model_version: null,
		input: {},
		output: {},
		pipeline_version: 'test',
		started_at: '2026-10-14T08:49:01Z',
		duration_ms: 1000,
		...extra
	};
}
