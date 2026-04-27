import { useNavigate } from 'react-router-dom';

const variantClasses = {
  default: 'border-gray-200',
  success: 'border-green-300 bg-green-50',
  warning: 'border-amber-300 bg-amber-50',
  danger: 'border-red-300 bg-red-50',
};

export default function KPICard({ title, value, subtitle, icon, navigateTo, navParams = {}, variant = 'default', color }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (!navigateTo) return;
    const params = new URLSearchParams();
    Object.entries(navParams).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.set(k, v);
    });
    const qs = params.toString();
    navigate(`${navigateTo}${qs ? '?' + qs : ''}`);
  };

  const borderAccent = color ? `border-l-4 ${color}` : '';

  return (
    <div
      className={`rounded-lg border p-4 flex flex-col gap-1 ${variantClasses[variant]} ${borderAccent} ${navigateTo ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={navigateTo ? handleClick : undefined}
      role={navigateTo ? 'button' : undefined}
    >
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{title}</span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
    </div>
  );
}
