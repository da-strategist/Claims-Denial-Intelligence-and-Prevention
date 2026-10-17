import { useId } from 'react'
import { INPUT_CLASS } from '../constants'
import { passwordProblems } from '../utils/password'
import Icon from './Icon'

export default function PasswordFields({ password, confirm, onChange, autoFocus = false }) {
  const base = useId()
  const problems = passwordProblems(password, confirm)
  const rules = ['At least 12 characters', 'Upper- and lower-case letters', 'A digit or symbol', 'Both passwords match']
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label htmlFor={`${base}-pw`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Password</span>
          <input
            id={`${base}-pw`}
            type="password"
            autoComplete="new-password"
            autoFocus={autoFocus}
            className={INPUT_CLASS}
            value={password}
            onChange={(e) => onChange({ password: e.target.value, confirm })}
          />
        </label>
        <label htmlFor={`${base}-confirm`} className="space-y-1 text-sm font-medium text-gray-800">
          <span className="block">Repeat password</span>
          <input
            id={`${base}-confirm`}
            type="password"
            autoComplete="new-password"
            className={INPUT_CLASS}
            value={confirm}
            onChange={(e) => onChange({ password, confirm: e.target.value })}
          />
        </label>
      </div>
      <ul aria-label="Password requirements" className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {rules.map((rule) => {
          const met = password !== '' && !problems.includes(rule)
          return (
            <li key={rule} className={`flex items-center gap-1 ${met ? 'text-emerald-700' : 'text-gray-500'}`}>
              <Icon name={met ? 'check' : 'close'} className="h-3.5 w-3.5" strokeWidth={2} />
              {rule}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
