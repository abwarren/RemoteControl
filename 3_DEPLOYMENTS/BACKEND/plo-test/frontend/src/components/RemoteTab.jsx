export default function RemoteTab() {
  return (
    <iframe
      src="/remote"
      style={{
        width: '100%',
        height: 'calc(100vh - 64px)',
        border: 'none',
        borderRadius: '8px',
      }}
      title="Remote Control"
    />
  )
}
