
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useForm, Controller } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Sheet,
    SheetContent,
} from "@/components/ui/sheet";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { ChevronRight, ChevronDown, Folder, FolderOpen, Paperclip, Copy, CheckCircle2, XCircle, Loader2, Search, User, ShoppingBag, Hammer, Package, Factory, Flame, BadgeCheck, Banknote, Landmark, TrendingUp, TrendingDown, MoreHorizontal, Crown } from 'lucide-react';
import LedgerDocuments from "@/components/shared/LedgerDocuments";
import { Checkbox } from "@/components/ui/checkbox";
import { renderErrorTree } from "@/Utils";
import { createLedger, getAccountGroup, getStates, getLedger, updateLedger, getTypes, addLedgerRole, removeLedgerRole, setPrimaryLedgerRole, fetchTDSSections, checkLedgerName, fetchB2BPricelists, fetchRetailDiscountPricelists, uploadLedgerDocument } from '@/services/apiService';
import PhoneInput, { makePhoneValidator } from "@/components/ui/PhoneInput";
import Fuse from 'fuse.js';
import { useSpellCheck } from '@/hooks/useSpellCheck';
import { useF4Submit } from '@/hooks/useF4Submit';

// ─── Account tree helpers ─────────────────────────────────────────────────────

function buildAccountTree(flatList) {
    const map = {};
    const roots = [];
    flatList.forEach(item => { map[item.id] = { ...item, children: [] }; });
    flatList.forEach(item => {
        if (item.parent && map[item.parent]) {
            map[item.parent].children.push(map[item.id]);
        } else if (!item.parent) {
            roots.push(map[item.id]);
        }
    });
    return roots;
}

// FA asset account group codes
const FA_ASSET_CODES = new Set(['FA-LB', 'FA-PM', 'FA-FF', 'FA-CE', 'FA-VH']);

// IT block categories valid for each FA group (mirrors backend _IT_BLOCK_TO_FA_GROUP)
const FA_GROUP_IT_BLOCKS = {
    'FA-LB': [
        { value: 'BLDG_RES', label: 'Residential Building (5%)' },
        { value: 'BLDG_COM', label: 'Commercial Building (10%)' },
    ],
    'FA-FF': [
        { value: 'FURN', label: 'Furniture & Fixtures (10%)' },
    ],
    'FA-PM': [
        { value: 'PLANT',  label: 'Plant & Machinery (15%)' },
        { value: 'BOOKS',  label: 'Books (100%)' },
        { value: 'INTANG', label: 'Intangible Assets (25%)' },
    ],
    'FA-VH': [
        { value: 'VEHICLE', label: 'Vehicles (15%)' },
    ],
    'FA-CE': [
        { value: 'COMPUTER', label: 'Computers & Software (40%)' },
    ],
};

// Default WDV rates by IT block (used to pre-fill the rate field)
const IT_BLOCK_DEFAULT_RATE = {
    BLDG_RES: 5, BLDG_COM: 10, FURN: 10,
    PLANT: 15, VEHICLE: 15, COMPUTER: 40,
    BOOKS: 100, INTANG: 25,
};

// Hints shown on hover � examples of ledgers that belong under each account group
const GROUP_HINTS = {
    'CA-CSH':     'e.g. Cash, Petty Cash',
    'CA-BNK':     'e.g. HDFC Bank, Kotak Bank, SBI Current A/c',
    'CA-BNK-OD':  'e.g. Bank Overdraft accounts',
    'CA-CHQ':     'e.g. Cheques in Hand (system ledger)',
    'CA-STK':     'e.g. Stock-in-Hand, Stock-in-Transit',
    'CA-SD':      'e.g. Customer / Debtor accounts (B2C & B2B)',
    'CA-GST':     'e.g. Input CGST, Input SGST, Input IGST',
    'CA-DEP':     'e.g. Security Deposits, EMD, Rental Deposit',
    'CA-LA':      'e.g. Loans given, Staff Advances, Advance Income Tax',
    'FA-LB':      'Managed via Fixed Assets > Asset Master',
    'FA-PM':      'Managed via Fixed Assets > Asset Master',
    'FA-FF':      'Managed via Fixed Assets > Asset Master',
    'FA-CE':      'Managed via Fixed Assets > Asset Master',
    'FA-VH':      'Managed via Fixed Assets > Asset Master',
    'FA-AD':      'e.g. Accumulated Depreciation (contra-asset)',
    'INV':        'e.g. Mutual Funds, Fixed Deposits, Gold Investments',
    'CL-SC':      'e.g. Supplier / Vendor / Karigar accounts',
    'CL-DT':      'e.g. Duties & Taxes payable',
    'CL-DT-GST':  'e.g. Output CGST, Output SGST, Output IGST',
    'CL-DT-TDS':  'e.g. TDS Payable, TDS on Salary',
    'CL-DT-TCS':  'e.g. TCS Payable',
    'CL-PRV':     'e.g. Provision for Expenses, Provision for Tax',
    'CL-HR':      'e.g. HR & Payroll Liabilities',
    'CL-HR-SAL':  'e.g. Salary Payable, Employee Payable',
    'CL-HR-PF':   'e.g. PF Payable',
    'CL-HR-ESI':  'e.g. ESI Payable',
    'CL-HR-PT':   'e.g. Professional Tax Payable',
    'LL-SEC':     'e.g. Term Loans, Vehicle Loans, Mortgage',
    'LL-USEC':    'e.g. Partner Loans, Director Loans',
    'CAP-OWN':    "e.g. Owner's Capital, Partner Capital",
    'CAP-RES':    'e.g. Retained Earnings, General Reserve, P&L A/c',
    'INC-DIR-SAL':'e.g. Gold Sales, Diamond Sales, Ornament Sales, Making Charge Received',
    'INC-IND':    'e.g. Interest Received, Discount Received, Commission Received',
    'EXP-DIR-PUR':'e.g. Gold Purchase, Diamond Purchase, Silver Purchase',
    'EXP-DIR-MFG':'e.g. Manufacturing Wages, Polish/Finish Costs',
    'EXP-DIR-MKG':'e.g. Making Charges Paid to Karigars',
    'EXP-DIR-STN':'e.g. Stone Setting, Stone Cost',
    'EXP-DIR-FRT':'e.g. Freight Inward, Carriage Inward, Courier Charges',
    // Indirect Expense sub-groups
    'EXP-IND-ADM':'e.g. Office Rent, Electricity, Stationery, Bank Charges, Professional Fees, Software Expenses',
    'EXP-IND-SND':'e.g. Showroom Rent, Packaging, Courier, Commission to Agents, Exhibition Expenses',
    'EXP-IND-MKT':'e.g. Digital Marketing, Influencer Marketing, Photoshoots, Branding, Hoardings',
    'EXP-IND-SHW':'e.g. Showroom Maintenance, Interior Decor, Security, Housekeeping, AC & Lighting',
    'EXP-IND-HR': 'e.g. Salary & Wages, Staff Welfare, Training, Recruitment, PF/ESI, Bonus',
    'EXP-IND-RPM':'e.g. Equipment Maintenance, Computer/IT Maintenance, Furniture Repairs, AMC',
    'EXP-IND-TRV':'e.g. Local Travel, Business Travel, Fuel, Vehicle Maintenance',
    'EXP-IND-FIN':'e.g. Interest on Loans/OD, Processing Fees, Discounting Charges, Credit Card Charges',
    'EXP-IND-CMP':'e.g. GST Filing Fees, Audit Fees, Licensing, Hallmark Registration, Penalties',
    'EXP-IND-INS':'e.g. Stock Insurance, Fire Insurance, Burglary Insurance, Employee Insurance',
    'EXP-IND-IT': 'e.g. Cloud Hosting, SaaS Subscriptions, Cybersecurity, POS Systems',
    'EXP-IND-MSC':'e.g. Donations, Festival Expenses, General Expenses, Rounding Off',
};

// Suggest the best account group code for a given ledger name
const GROUP_SUGGEST_KEYWORDS = [
    { keywords: ['rent', 'office rent'],                               code: 'EXP-IND-ADM' },
    { keywords: ['electricity', 'power', 'utility'],                   code: 'EXP-IND-ADM' },
    { keywords: ['stationery', 'printing'],                            code: 'EXP-IND-ADM' },
    { keywords: ['bank charge'],                                       code: 'EXP-IND-ADM' },
    { keywords: ['professional fee', 'legal fee', 'consultant'],       code: 'EXP-IND-ADM' },
    { keywords: ['software', 'erp'],                                   code: 'EXP-IND-ADM' },
    { keywords: ['internet', 'telephone', 'communication'],            code: 'EXP-IND-ADM' },
    { keywords: ['showroom rent', 'packaging', 'courier', 'delivery'], code: 'EXP-IND-SND' },
    { keywords: ['commission', 'broker', 'agent'],                     code: 'EXP-IND-SND' },
    { keywords: ['exhibition', 'trade show'],                          code: 'EXP-IND-SND' },
    { keywords: ['e-commerce', 'platform fee'],                        code: 'EXP-IND-SND' },
    { keywords: ['marketing', 'google ad', 'meta ad', 'digital ad'],   code: 'EXP-IND-MKT' },
    { keywords: ['influencer', 'affiliate'],                           code: 'EXP-IND-MKT' },
    { keywords: ['photoshoot', 'catalog', 'branding', 'design cost'],  code: 'EXP-IND-MKT' },
    { keywords: ['hoarding', 'outdoor', 'billboard'],                  code: 'EXP-IND-MKT' },
    { keywords: ['website', 'web develop'],                            code: 'EXP-IND-MKT' },
    { keywords: ['advertisement', 'publicity', 'campaign'],            code: 'EXP-IND-MKT' },
    { keywords: ['showroom maintenance', 'interior', 'visual merchandis'], code: 'EXP-IND-SHW' },
    { keywords: ['security service', 'housekeeping', 'air conditioning'], code: 'EXP-IND-SHW' },
    { keywords: ['salary', 'wage', 'staff welfare', 'uniform'],        code: 'EXP-IND-HR' },
    { keywords: ['training', 'recruitment', 'bonus', 'incentive'],     code: 'EXP-IND-HR' },
    { keywords: ['pf ', 'esi ', 'gratuity'],                           code: 'EXP-IND-HR' },
    { keywords: ['repair', 'maintenance', 'amc'],                     code: 'EXP-IND-RPM' },
    { keywords: ['equipment maintenance', 'computer maintenance'],     code: 'EXP-IND-RPM' },
    { keywords: ['furniture repair'],                                  code: 'EXP-IND-RPM' },
    { keywords: ['travel', 'conveyance', 'fuel', 'vehicle'],           code: 'EXP-IND-TRV' },
    { keywords: ['flight', 'hotel', 'business travel'],                code: 'EXP-IND-TRV' },
    { keywords: ['interest paid', 'interest on loan', 'interest on od'], code: 'EXP-IND-FIN' },
    { keywords: ['processing fee', 'discounting', 'credit card charge'], code: 'EXP-IND-FIN' },
    { keywords: ['gst filing', 'audit fee', 'licensing', 'hallmark reg'], code: 'EXP-IND-CMP' },
    { keywords: ['government charge', 'penalty', 'regulatory'],        code: 'EXP-IND-CMP' },
    { keywords: ['insurance', 'fire insurance', 'burglary', 'stock insurance'], code: 'EXP-IND-INS' },
    { keywords: ['cloud', 'hosting', 'saas', 'subscription', 'cybersecurity', 'pos system'], code: 'EXP-IND-IT' },
    { keywords: ['donation', 'festival expense', 'diwali', 'general expense', 'rounding off', 'miscellaneous'], code: 'EXP-IND-MSC' },
    { keywords: ['depreciation'],                                      code: 'EXP-IND' },
    { keywords: ['interest received', 'discount received'],            code: 'INC-IND' },
    { keywords: ['freight', 'carriage'],                               code: 'EXP-DIR-FRT' },
    { keywords: ['purchase'],                                          code: 'EXP-DIR-PUR' },
    { keywords: ['sale', 'making charge received'],                    code: 'INC-DIR-SAL' },
];

function suggestGroupCode(ledgerName) {
    if (!ledgerName) return null;
    const lower = ledgerName.toLowerCase();
    // Try longest keyword match first
    let bestMatch = null;
    let bestLen = 0;
    for (const rule of GROUP_SUGGEST_KEYWORDS) {
        for (const kw of rule.keywords) {
            if (lower.includes(kw) && kw.length > bestLen) {
                bestMatch = rule.code;
                bestLen = kw.length;
            }
        }
    }
    return bestMatch;
}

// Roles that cannot be combined with any other role
const EXCLUSIVE_ROLES = new Set(['CA', 'BA', 'INC', 'EXP']);

// ─── Role metadata � icons, descriptions, grouping ──────────────────────────

const ROLE_META = {
    CO:  { Icon: User,           group: 'party',   desc: 'Retail buyer'                    },
    DL:  { Icon: ShoppingBag,    group: 'party',   desc: 'Wholesale buyer'                 },
    KR:  { Icon: Hammer,         group: 'party',   desc: 'Artisan / job-work'              },
    VD:  { Icon: Package,        group: 'party',   desc: 'Goods & services supplier'       },
    REF: { Icon: Factory,        group: 'party',   desc: 'Precious metal refinery'         },
    MLT: { Icon: Flame,          group: 'party',   desc: 'Metal melting & processing'      },
    HM:  { Icon: BadgeCheck,     group: 'party',   desc: 'Hallmark certification body'     },
    CA:  { Icon: Banknote,       group: 'account', desc: 'Physical cash account'           },
    BA:  { Icon: Landmark,       group: 'account', desc: 'Bank account'                    },
    INC: { Icon: TrendingUp,     group: 'account', desc: 'Revenue / income ledger'         },
    EXP: { Icon: TrendingDown,   group: 'account', desc: 'Expense ledger'                  },
    OTH: { Icon: MoreHorizontal, group: 'account', desc: 'Miscellaneous ledger'            },
};

const GroupPickerNode = ({ node, level, onSelect, suggestedCode, allowFa = false }) => {
    const hasChildren = node.children?.length > 0;
    const [open, setOpen] = useState(level === 0);
    const indent = level * 20;
    const isFaGroup = FA_ASSET_CODES.has(node.code);
    // Block FA groups only when allowFa is false (create mode / no reclassification)
    const isBlocked = isFaGroup && !allowFa;
    const hint = GROUP_HINTS[node.code];
    const isSuggested = suggestedCode && node.code === suggestedCode;

    function handleClick() {
        if (isBlocked) return;
        onSelect(node);
    }

    return (
        <div>
            <div
                className={`group flex items-center gap-2 py-2 pr-3 rounded-lg transition-colors relative ${
                    isBlocked ? 'opacity-40 cursor-not-allowed' :
                    isSuggested ? 'bg-green-50 ring-1 ring-green-300 hover:bg-green-100 cursor-pointer' :
                    'hover:bg-violet-50 cursor-pointer'
                }`}
                style={{ paddingLeft: `${indent + 8}px` }}
                onClick={handleClick}
                title={isBlocked ? `Use Fixed Assets → Asset Master to add ledgers under ${node.name}` : hint || undefined}
            >
                {hasChildren ? (
                    <button
                        type="button"
                        className="shrink-0 size-5 flex items-center justify-center rounded hover:bg-violet-100 text-primary"
                        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
                    >
                        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                ) : (
                    <span className="size-5 shrink-0 flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                    </span>
                )}
                {hasChildren
                    ? open
                        ? <FolderOpen className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-violet-400'}`} />
                        : <Folder className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-violet-400'}`} />
                    : null
                }
                {node.code && (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 tracking-wider ${level === 0 ? 'bg-violet-200 text-primary' : 'bg-gray-100 text-gray-500'}`}>
                        {node.code}
                    </span>
                )}
                <div className="flex flex-col min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                        <span className={`text-sm truncate ${level === 0 ? 'font-semibold text-primary' : 'text-gray-700'} group-hover:text-primary`}>
                            {node.name}
                        </span>
                        {isSuggested && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-green-200 text-green-800 shrink-0 uppercase tracking-wider">
                                Suggested
                            </span>
                        )}
                        {isFaGroup && allowFa && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 shrink-0 uppercase tracking-wider">
                                Fixed Asset
                            </span>
                        )}
                    </div>
                    {hint && (
                        <span className="text-[10px] text-gray-400 truncate leading-tight mt-0.5">
                            {hint}
                        </span>
                    )}
                </div>
                {hasChildren && (
                    <span className="ml-auto text-[10px] text-gray-400 shrink-0">{node.children.length}</span>
                )}
            </div>
            {open && hasChildren && (
                <div className={level === 0 ? 'ml-3 border-l border-violet-100 pl-1 mb-1' : 'ml-3 border-l border-gray-100 pl-1'}>
                    {node.children.map(child => (
                        <GroupPickerNode key={child.id} node={child} level={level + 1} onSelect={isBlocked ? () => {} : onSelect} suggestedCode={suggestedCode} allowFa={allowFa} />
                    ))}
                </div>
            )}
        </div>
    );
};

// ─── Primitives ───────────────────────────────────────────────────────────────

const SectionCard = ({ number, title, children }) => (
    <div className="rounded-xl border border-violet-100 bg-white shadow-sm overflow-hidden">
        {/* Card header */}
        <div className="flex items-center gap-3 px-7 py-4 bg-violet-50 border-b border-violet-100">
            <span className="flex items-center justify-center size-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">
                {number}
            </span>
            <span className="text-sm font-bold text-primary tracking-widest uppercase">
                {title}
            </span>
        </div>
        {/* Card body */}
        <div className="px-7 py-6 space-y-6">
            {children}
        </div>
    </div>
);

const Field = ({ label, required, error, children }) => (
    <div className="flex flex-col gap-2">
        <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
            {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
        {children}
        {error && <p className="text-xs text-red-500 -mt-1">{error}</p>}
    </div>
);

// ─── Component ────────────────────────────────────────────────────────────────

const LedgerForm = () => {
    const { id } = useParams();
    const { toast } = useToast();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const nextUrl = searchParams.get("next"); // e.g. /sales/customerorder/list/add/
    const acGroupBtnRef = React.useRef(null);

    const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { errors, isDirty } } = useForm({
        defaultValues: {
            salutation: 'none',
            ac_name: '',
            display_name: '',
            b2b: 'na',
            ac_group: '',
            dob: '',
            anniversary: '',
            add1: '',
            add2: '',
            city: '',
            pincode: '',
            state: 'none',
            ship_add1: '',
            ship_add2: '',
            ship_city: '',
            ship_pincode: '',
            ship_state: 'none',
            phone1: '',
            phone2: '',
            phone3: '',
            mobile1: '',
            mobile2: '',
            mobile3: '',
            fax: '',
            email: '',
            pan: '',
            gst: '',
            aadhar: '',
            passport: '',
            dl_no: '',
            remarks: '',
            tds_applicable: false,
            tds_section: '',
            tds_deductor_type: '',
            b2b_pricelist: '',
            retail_discount_pricelist: '',
        },
    });

    const [states, setStates] = useState([]);
    const [pricelists, setPricelists] = useState([]);
    const [retailDiscountPricelists, setRetailDiscountPricelists] = useState([]);
    const [shippingSameAsBilling, setShippingSameAsBilling] = useState(true);
    const [accounts, setAccounts] = useState([]);
    const [accountTree, setAccountTree] = useState([]);
    const [types, setTypes] = useState([]);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [groupSearch, setGroupSearch] = useState('');
    const spellCheckEnabled = useSpellCheck();
    // ledgerRoles: array of { role, is_primary }
    const [ledgerRoles, setLedgerRoles] = useState([]);
    const [roleLoading, setRoleLoading] = useState(null);  // role code being toggled
    const [groupAutoFilled, setGroupAutoFilled] = useState(false); // true when account group was set by role
    const [tdsSections, setTdsSections] = useState([]);
    const [nameCheck, setNameCheck] = useState({ checking: false, exists: null }); // null = not checked yet
    const [pendingDocs, setPendingDocs] = useState([]);
    const nameCheckTimer = React.useRef(null);
    // Tracks whether the user has manually edited Display Name.
    // Starts true in edit-mode (don't overwrite existing value) and false for new ledgers.
    const displayNameTouched = React.useRef(!!id);
    // Prevents the role-based b2b auto-set from firing on the initial data load
    // (we want to preserve the saved value, not override it on mount).
    const skipB2bAutoset = React.useRef(false);

    // ── FA reclassification state ──────────────────────────────────────────────
    // Holds field.onChange from the ac_group Controller so handleGroupPickerSelect can call it
    const groupFieldOnChange = React.useRef(null);
    const [faModalOpen, setFaModalOpen] = useState(false);
    const [pendingFaGroup, setPendingFaGroup] = useState(null); // node user clicked
    const [faDetails, setFaDetails] = useState({
        purchase_date: '', purchase_cost: '', residual_value: '0',
        it_block_category: '', depreciation_method: 'WDV', rate_or_life: '', description: '',
    });
    // Set to true once FA modal is confirmed; triggers fa_data inclusion in payload
    const [faDetailsConfirmed, setFaDetailsConfirmed] = useState(false);
    const [faRemoveConfirmOpen, setFaRemoveConfirmOpen] = useState(false);
    const [pendingNonFaGroup, setPendingNonFaGroup] = useState(null); // node user clicked (FA→non-FA)
    // ── end FA reclassification state ─────────────────────────────────────────

    // ── FA reclassification: intercept group picker selection ─────────────────
    const handleGroupPickerSelect = useCallback((node) => {
        const isNewFa = FA_ASSET_CODES.has(node.code);
        const currentGroupId = getValues('ac_group');
        const currentGroup = accounts.find(a => a.id.toString() === currentGroupId);
        const isOldFa = currentGroup && FA_ASSET_CODES.has(currentGroup.code);

        // Expense → FA: open FA details modal (edit mode only)
        if (id && isNewFa && !isOldFa) {
            setPendingFaGroup(node);
            setFaDetails({ purchase_date: '', purchase_cost: '', residual_value: '0', it_block_category: '', depreciation_method: 'WDV', rate_or_life: '', description: '' });
            setFaDetailsConfirmed(false);
            setFaModalOpen(true);
            setPickerOpen(false);
            return;
        }
        // FA → Expense: open remove confirmation dialog (edit mode only)
        if (id && !isNewFa && isOldFa) {
            setPendingNonFaGroup(node);
            setFaRemoveConfirmOpen(true);
            setPickerOpen(false);
            return;
        }
        // Normal selection (FA→FA, non-FA→non-FA, or create mode)
        groupFieldOnChange.current?.(node.id.toString());
        setGroupAutoFilled(false);
        setPickerOpen(false);
        setGroupSearch('');
    }, [id, accounts, getValues]);
    // ── end handleGroupPickerSelect ────────────────────────────────────────────

    // Derived helpers
    // useMemo keeps the array reference stable when ledgerRoles hasn't changed,
    // preventing the b2b auto-set useEffect from firing on every render.
    const activeRoleCodes = useMemo(() => ledgerRoles.map(r => r.role ?? r), [ledgerRoles]);
    const primaryRole = (ledgerRoles.find(r => r.is_primary)?.role)
        ?? (ledgerRoles[0]?.role ?? ledgerRoles[0]);              // fallback to first

    const NON_CUSTOMER_ROLES = ['DL','KR','VD','CA','BA','SC','SD','REF','EXP','INC','HM','OTH'];
    const hasNonCustomerRole = activeRoleCodes.some(r => NON_CUSTOMER_ROLES.includes(r));

    // Fuzzy-filtered flat account list for the group picker search box
    const filteredAccounts = useMemo(() => {
        if (!groupSearch.trim() || !spellCheckEnabled) return null; // null = show tree view
        const fuse = new Fuse(accounts, {
            keys: ['name', 'code'],
            threshold: 0.4,
            minMatchCharLength: 2,
        });
        return fuse.search(groupSearch.trim()).map(r => r.item);
    }, [groupSearch, accounts, spellCheckEnabled]);

    const acName = watch('ac_name');

    // Auto-mirror ac_name → display_name for new ledgers until user edits display_name manually
    useEffect(() => {
        if (!displayNameTouched.current) {
            setValue('display_name', acName, { shouldValidate: false, shouldDirty: false });
        }
    }, [acName, setValue]);

    // Auto-set Business Type based on active roles:
    //   DL (dealer) → always B2B ('true')
    //   neither CO nor DL → Not Applicable ('na')
    //   CO only → leave current value (user chooses Retail/Wholesale)
    useEffect(() => {
        if (skipB2bAutoset.current) {
            skipB2bAutoset.current = false;
            return;
        }
        const hasDL = activeRoleCodes.includes('DL');
        const hasCO = activeRoleCodes.includes('CO');
        if (hasDL) {
            setValue('b2b', 'true', { shouldValidate: false });
        } else if (!hasCO) {
            setValue('b2b', 'na', { shouldValidate: false });
        } else {
            // CO only: if previously N/A (e.g. role just changed to CO), default to B2C
            const current = getValues('b2b');
            if (current === 'na') setValue('b2b', 'false', { shouldValidate: false });
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeRoleCodes]);

    // Real-time ledger name uniqueness check (only for non-customer ledgers)
    useEffect(() => {
        if (nameCheckTimer.current) clearTimeout(nameCheckTimer.current);
        if (!hasNonCustomerRole || !acName || acName.trim().length < 2) {
            setNameCheck({ checking: false, exists: null });
            return;
        }
        setNameCheck({ checking: true, exists: null });
        nameCheckTimer.current = setTimeout(async () => {
            const res = await checkLedgerName(acName.trim(), id || null);
            setNameCheck({ checking: false, exists: res.exists });
        }, 500);
        return () => clearTimeout(nameCheckTimer.current);
    }, [acName, hasNonCustomerRole, id]);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [statesRes, typesRes, accountsRes] = await Promise.all([
                    getStates(),
                    getTypes(),
                    getAccountGroup(),
                ]);
                setStates(statesRes.data);
                setTypes(typesRes.data);
                setAccounts(accountsRes.data);
                setAccountTree(buildAccountTree(accountsRes.data));

                const [tdsRes, plRes, rdplRes] = await Promise.all([
                    fetchTDSSections(),
                    fetchB2BPricelists(),
                    fetchRetailDiscountPricelists(),
                ]);
                if (tdsRes.success) {
                    const d = tdsRes.data;
                    setTdsSections(Array.isArray(d) ? d : d?.results ?? []);
                }
                if (plRes.success) {
                    const d = plRes.data;
                    setPricelists((Array.isArray(d) ? d : d?.results ?? []).filter(p => p.is_active));
                }
                if (rdplRes.success) {
                    const d = rdplRes.data;
                    setRetailDiscountPricelists((Array.isArray(d) ? d : d?.results ?? []).filter(p => p.is_active));
                }

                if (id) {
                    displayNameTouched.current = true; // editing � never auto-override
                    const { data } = await getLedger(id);
                    // Determine if shipping address differs from billing
                    const shipDiffers = (
                        (data.ship_add1 && data.ship_add1 !== data.add1) ||
                        (data.ship_add2 && data.ship_add2 !== data.add2) ||
                        (data.ship_city && data.ship_city !== data.city) ||
                        (data.ship_pincode && data.ship_pincode !== data.pincode) ||
                        (data.ship_state && data.ship_state !== data.state)
                    );
                    setShippingSameAsBilling(!shipDiffers);
                    // Derive b2b display value: true→'true', false→'false' only if
                    // ledger has a CO/DL role, otherwise 'na'.
                    const hasB2bRole = (data.roles || []).some(r =>
                        ['CO', 'DL'].includes(r.role ?? r)
                    );
                    const b2bDisplay = data.b2b ? 'true' : (hasB2bRole ? 'false' : 'na');
                    reset({
                        ...data,
                        b2b: b2bDisplay,
                        b2b_pricelist: data.b2b_pricelist ? String(data.b2b_pricelist) : '',
                        retail_discount_pricelist: data.retail_discount_pricelist ? String(data.retail_discount_pricelist) : '',
                        dob: data.dob || '',
                        anniversary: data.anniversary || '',
                        ac_group: data.ac_group?.toString() || '',
                        tds_applicable: data.tds_applicable ?? false,
                        tds_section: data.tds_section ? String(data.tds_section) : '',
                        tds_deductor_type: data.tds_deductor_type ?? '',
                        // If no shipping data yet, mirror billing
                        ship_add1:    data.ship_add1    || data.add1    || '',
                        ship_add2:    data.ship_add2    || data.add2    || '',
                        ship_city:    data.ship_city    || data.city    || '',
                        ship_pincode: data.ship_pincode || data.pincode || '',
                        ship_state:   data.ship_state   || data.state   || 'none',
                    });
                    // Load existing roles � skip the role-based b2b auto-set on this render
                    skipB2bAutoset.current = true;
                    setLedgerRoles(data.roles || []);
                }
            } catch (error) {
                console.error("Error loading ledger form:", error);
                toast({ title: "Error", description: "Failed to load form data." });
            }
        };
        fetchAll();
    }, [id, reset]);



    const validatePhone    = makePhoneValidator();
    const validatePAN      = (v) => !v || /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(v)       || 'Invalid PAN � expected format: ABCDE1234F';
    const validateGST      = (v) => !v || /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}Z[0-9A-Z]{1}$/.test(v) || 'Invalid GST � expected format: 22AAAAA0000A1Z5';
    const validateAadhar   = (v) => !v || /^[0-9]{12}$/.test(v)                        || 'Aadhar must be exactly 12 digits';
    const validatePassport = (v) => !v || /^[A-Z][0-9]{7}$/.test(v)                    || 'Invalid passport � expected format: A1234567';

    useF4Submit(() => handleSubmit(onSubmit)());

    const onSubmit = async (data) => {
        if (activeRoleCodes.length === 0) {
            toast({ title: "Select at least one role", description: "Every ledger must have at least one role.", variant: "destructive" });
            return;
        }
        if (!data.ac_group) {
            toast({ title: "Account group is required", description: "Every ledger must belong to an account group. Please select one.", variant: "destructive" });
            return;
        }
        if (nameCheck.exists === true) {
            toast({ title: "Duplicate ledger name", description: "A ledger with this name already exists. Please use a different name.", variant: "destructive" });
            return;
        }
        try {
            const payload = {
                ...data,
                b2b: data.b2b === 'true',
                b2b_pricelist: data.b2b_pricelist ? Number(data.b2b_pricelist) : null,
                retail_discount_pricelist: data.retail_discount_pricelist ? Number(data.retail_discount_pricelist) : null,
                dob: data.dob || null,
                anniversary: data.anniversary || null,
                // Include FA details if user confirmed reclassification to FA group
                ...(faDetailsConfirmed ? { fa_data: faDetails } : {}),
            };
            const response = id ? await updateLedger(id, payload) : await createLedger(payload);
            if (response.success) {
                const newId = response.data?.id ?? id;
                // For new ledgers, sync locally-chosen roles to the API
                if (!id && newId) {
                    for (const r of ledgerRoles) {
                        const roleCode = r.role ?? r;
                        await addLedgerRole(newId, roleCode);
                    }
                    // Set primary role
                    const primary = ledgerRoles.find(r => r.is_primary)?.role ?? ledgerRoles[0]?.role ?? ledgerRoles[0];
                    if (primary) await setPrimaryLedgerRole(newId, primary);
                    // Upload any queued documents
                    for (const { file, docType } of pendingDocs) {
                        await uploadLedgerDocument(newId, file, docType);
                    }
                    setPendingDocs([]);
                }

                // FA reclassification success notices
                if (response.data?.fa_record_created) {
                    toast({ title: "Fixed Asset registered", description: "A Fixed Asset record has been created � view it in Fixed Assets → Asset Master." });
                } else if (response.data?.fa_record_deleted) {
                    toast({ title: "Fixed Asset removed", description: "The Fixed Asset record has been deleted. The ledger has been moved to the new group." });
                } else {
                    toast({ title: "Success", description: `Ledger ${id ? 'updated' : 'created'} successfully.` });
                }
                // Reset FA reclassification state
                setFaDetailsConfirmed(false);
                setPendingFaGroup(null);
                setPendingNonFaGroup(null);

                setTimeout(() => {
                    // If opened from another page (e.g. Customer Order form), redirect back with new ledger info
                    if (!id && nextUrl) {
                        const qs = new URLSearchParams({
                            ldgr: newId,
                            ldgr_name: payload.ac_name ?? "",
                        }).toString();
                        navigate(`${nextUrl}?${qs}`);
                    } else {
                        navigate("/crm/ledger");
                    }
                }, 1200);
            } else {
                toast({ title: "Submission failed", description: renderErrorTree(response.error) });
            }
        } catch (error) {
            console.error('Error submitting ledger:', error);
            toast({ title: "Error", description: "Failed to save ledger. Please try again." });
        }
    };

    // Auto-fill Account Group based on primary role (only in create mode; always updates on role change)
    const autoFillAccountGroup = (newRoles) => {
        if (id) return; // edit mode: don't override saved data
        const primary = (newRoles.find(r => r.is_primary)?.role) ?? newRoles[0]?.role;
        if (!primary) return;
        const ROLE_GROUP = {
            'CO':  'Sundry Debtors',
            'DL':  'Sundry Debtors',
            'SD':  'Sundry Debtors',
            'VD':  'Sundry Creditors',
            'KR':  'Sundry Creditors',
            'SC':  'Sundry Creditors',
            'CA':  'Cash-in-Hand',
            'BA':  'Bank Accounts',
            'INC': 'Sales Account',
            'EXP': 'Indirect Expenses',
        };
        const targetName = ROLE_GROUP[primary];
        if (!targetName) return;
        const match = accounts.find(a => a.name?.toLowerCase() === targetName.toLowerCase());
        if (match) { setValue('ac_group', match.id.toString()); setGroupAutoFilled(true); }
    };

    const handleRoleToggle = async (roleCode, checked) => {
        setRoleLoading(roleCode);
        if (id) {
            // Edit mode � call API immediately
            const res = checked
                ? await addLedgerRole(id, roleCode)
                : await removeLedgerRole(id, roleCode);
            if (res.success) {
                setLedgerRoles(res.data.roles);
            } else {
                const msg = res.error?.error || res.error || 'Failed to update role';
                toast({ title: "Role update failed", description: String(msg), variant: "destructive" });
            }
        } else {
            // Create mode � manage locally; will be sent on first save
            setLedgerRoles(prev => {
                let next;
                if (checked) {
                    const alreadyExists = prev.some(r => (r.role ?? r) === roleCode);
                    if (alreadyExists) return prev;
                    const isFirst = prev.length === 0;
                    next = [...prev, { role: roleCode, is_primary: isFirst }];
                } else {
                    const filtered = prev.filter(r => (r.role ?? r) !== roleCode);
                    // If we removed the primary, promote the first remaining
                    const wasPrimary = prev.find(r => (r.role ?? r) === roleCode)?.is_primary;
                    if (wasPrimary && filtered.length > 0) {
                        filtered[0] = { ...filtered[0], is_primary: true };
                    }
                    next = filtered;
                }
                // Auto-fill account group based on new primary role
                setTimeout(() => autoFillAccountGroup(next), 0);
                return next;
            });
        }
        setRoleLoading(null);
    };

    const handleSetPrimary = async (roleCode) => {
        setRoleLoading(roleCode);
        if (id) {
            const res = await setPrimaryLedgerRole(id, roleCode);
            if (res.success) {
                setLedgerRoles(res.data.roles);
            } else {
                toast({ title: "Failed to set primary role", description: String(res.error?.error || res.error), variant: "destructive" });
            }
        } else {
            setLedgerRoles(prev => {
                const next = prev.map(r => ({ ...r, is_primary: (r.role ?? r) === roleCode }));
                setTimeout(() => autoFillAccountGroup(next), 0);
                return next;
            });
        }
        setRoleLoading(null);
    };

    const inputCls = "h-10 text-sm border-gray-200 focus:border-violet-400 focus:ring-violet-100";
    const triggerCls = "h-10 text-sm border-gray-200 focus:border-violet-400";

    return (
        <div className="max-w-4xl mx-auto pb-12">

            {/* ── Page header ─────────────────────────────────────────────── */}
            <div className="flex items-start justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                        {id ? 'Edit Ledger' : 'New Ledger'}
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">
                        {id
                            ? `Editing record #${id}`
                            : 'Create a new ledger account for a customer, supplier, or other party'}
                    </p>
                </div>
                <div className="flex gap-3 mt-1">
                    <Button type="button" variant="outline" onClick={() => navigate('/crm/ledger')} className="h-10 px-5">
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        form="ledgerForm"
                        disabled={!!id && !isDirty}
                        className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm"
                    >
                        {id ? 'Update Ledger' : 'Save Ledger'}
                    </Button>
                </div>
            </div>

            <form id="ledgerForm" onSubmit={handleSubmit(onSubmit)} className="space-y-6">

                {/* ── Section 1: Identity ──────────────────────────────────── */}
                <SectionCard number="1" title="Identity">

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                        <Field label="Salutation">
                            <Controller name="salutation" control={control} render={({ field }) => (
                                <Select onValueChange={field.onChange} value={field.value}>
                                    <SelectTrigger className={triggerCls}><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">� None �</SelectItem>
                                        <SelectItem value="shri">Shri</SelectItem>
                                        <SelectItem value="smt">Smt.</SelectItem>
                                        <SelectItem value="ms">Ms.</SelectItem>
                                        <SelectItem value="m/s">M/S.</SelectItem>
                                    </SelectContent>
                                </Select>
                            )} />
                        </Field>

                        <Field label="Party Name" required>
                            <div className="relative">
                                <Input
                                    className={`${inputCls} pr-8 ${nameCheck.exists ? 'border-red-400 focus:border-red-400' : nameCheck.exists === false && hasNonCustomerRole ? 'border-green-400 focus:border-green-400' : ''}`}
                                    {...register("ac_name")}
                                    required
                                    placeholder="Full legal name"
                                />
                                {hasNonCustomerRole && (
                                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
                                        {nameCheck.checking && <Loader2 className="size-4 text-gray-400 animate-spin" />}
                                        {!nameCheck.checking && nameCheck.exists === false && <CheckCircle2 className="size-4 text-green-500" />}
                                        {!nameCheck.checking && nameCheck.exists === true && <XCircle className="size-4 text-red-500" />}
                                    </span>
                                )}
                            </div>
                            {nameCheck.exists === true && (
                                <p className="text-xs text-red-500 -mt-1">A ledger with this name already exists.</p>
                            )}
                        </Field>

                        <Field label="Display Name" required>
                            <Input
                                className={inputCls}
                                {...register("display_name", {
                                    onChange: () => { displayNameTouched.current = true; },
                                })}
                                required
                                placeholder="Name on bills"
                            />
                        </Field>

                        <Field label="Business Type">
                            <Controller name="b2b" control={control} render={({ field }) => {
                                const hasDL = activeRoleCodes.includes('DL');
                                const hasCO = activeRoleCodes.includes('CO');
                                // Disabled when role makes the choice irrelevant or fixed:
                                //   DL  → always B2B, no override needed
                                //   neither CO nor DL → N/A, no choice makes sense
                                const isDisabled = hasDL || (!hasCO && !hasDL);
                                return (
                                    <Select
                                        onValueChange={field.onChange}
                                        value={field.value}
                                        disabled={isDisabled}
                                    >
                                        <SelectTrigger className={triggerCls}>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="na">Not Applicable</SelectItem>
                                            <SelectItem value="false">Retail (B2C)</SelectItem>
                                            <SelectItem value="true">Wholesale (B2B)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                );
                            }} />
                        </Field>

                        {watch('b2b') === 'true' && (
                            <Field label="B2B Pricelist">
                                <Controller name="b2b_pricelist" control={control} render={({ field }) => (
                                    <Select onValueChange={v => field.onChange(v === '__none__' ? '' : v)} value={field.value || '__none__'}>
                                        <SelectTrigger className={triggerCls}>
                                            <SelectValue placeholder="None" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="__none__">None</SelectItem>
                                            {pricelists.map(p => (
                                                <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )} />
                            </Field>
                        )}
                        <Field label="Retail Discount Pricelist">
                            <Controller name="retail_discount_pricelist" control={control} render={({ field }) => (
                                <Select onValueChange={v => field.onChange(v === '__none__' ? '' : v)} value={field.value || '__none__'}>
                                    <SelectTrigger className={triggerCls}>
                                        <SelectValue placeholder="None" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__none__">None</SelectItem>
                                        {retailDiscountPricelists.map(p => (
                                            <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            )} />
                        </Field>
                    </div>

                    {/* ── Roles � select role BEFORE account group ── */}
                    {types.length > 0 && (() => {
                        // Render in a fixed order: 7 party roles first, then 5 account roles = 12 cards, 4 per row
                        const orderedCodes = ['CO','DL','KR','VD','REF','MLT','HM','CA','BA','INC','EXP','OTH'];
                        const allOrdered = [
                            ...orderedCodes.map(code => types.find(t => t.code === code)).filter(Boolean),
                            ...types.filter(t => !orderedCodes.includes(t.code)), // any extras appended
                        ];

                        // True when an exclusive role (CA/BA/INC/EXP) is currently selected
                        const hasExclusiveActive = activeRoleCodes.some(r => EXCLUSIVE_ROLES.has(r));

                        const RoleCard = ({ t }) => {
                            const isChecked = activeRoleCodes.includes(t.code);
                            const isLoading = roleLoading === t.code;
                            const meta = ROLE_META[t.code];
                            const Icon = meta?.Icon;
                            const isAccount = meta?.group === 'account';
                            const locked = !!id && isChecked && primaryRole === t.code && activeRoleCodes.length === 1;
                            // Blocked when an exclusive role is active and this card is a different, unselected role
                            const blockedByExclusive = hasExclusiveActive && !isChecked;

                            // Party roles use violet when active; account roles use slate
                            const activeCard   = isAccount ? 'bg-slate-50 border-slate-300 shadow-sm'        : 'bg-violet-50 border-violet-300 shadow-sm';
                            const activeCircle = isAccount ? 'bg-slate-100'                                   : 'bg-violet-100';
                            const activeIcon   = isAccount ? 'text-slate-500'                                 : 'text-violet-600';
                            const activeName   = isAccount ? 'text-slate-600'                                 : 'text-violet-700';
                            const activeDesc   = isAccount ? 'text-slate-400'                                 : 'text-violet-400';
                            const activeTick   = isAccount ? 'text-slate-400'                                 : 'text-violet-500';

                            return (
                                <button
                                    type="button"
                                    disabled={isLoading || locked || blockedByExclusive}
                                    onClick={() => handleRoleToggle(t.code, !isChecked)}
                                    title={blockedByExclusive ? 'Remove the active Cash / Bank / Income / Expense role first' : undefined}
                                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border text-left transition-all select-none ${
                                        isChecked
                                            ? activeCard
                                            : blockedByExclusive
                                                ? 'bg-gray-50 border-gray-100 opacity-40 cursor-not-allowed'
                                                : 'bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                    } ${isLoading ? 'opacity-50 cursor-wait' : ''}`}
                                >
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                                        isChecked ? activeCircle : 'bg-gray-100'
                                    }`}>
                                        {isLoading
                                            ? <Loader2 className="size-4 text-gray-400 animate-spin" />
                                            : Icon
                                                ? <Icon className={`w-4 h-4 ${isChecked ? activeIcon : 'text-gray-400'}`} />
                                                : <span className={`text-[10px] font-bold ${isChecked ? activeIcon : 'text-gray-400'}`}>{t.code}</span>
                                        }
                                    </div>
                                    <div className="min-w-0">
                                        <p className={`text-xs font-semibold leading-none mb-0.5 ${isChecked ? activeName : 'text-gray-600'}`}>
                                            {t.name}
                                        </p>
                                        {meta?.desc && (
                                            <p className={`text-[10px] leading-tight ${isChecked ? activeDesc : 'text-gray-400'}`}>
                                                {meta.desc}
                                            </p>
                                        )}
                                    </div>
                                    {isChecked && <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 ml-auto ${activeTick}`} />}
                                </button>
                            );
                        };

                        return (
                            <div className="border-t border-gray-100 pt-4 space-y-4">
                                <div>
                                    <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-0.5">
                                        Ledger Roles
                                    </p>
                                    <p className="text-xs text-gray-400">
                                        Select one or more roles. A ledger with multiple roles appears in all relevant lists.
                                    </p>
                                </div>

                                {/* 12 cards in a 4-column grid � 3 rows of 4 */}
                                <div className="grid grid-cols-4 gap-2">
                                    {allOrdered.map(t => <RoleCard key={t.code} t={t} />)}
                                </div>

                                {/* Exclusive-role notice */}
                                {hasExclusiveActive && (
                                    <p className="text-[11px] text-amber-600 bg-amber-50 border border-amber-100 rounded px-2.5 py-1.5">
                                        Cash, Bank, Income and Expense ledgers cannot be combined with other roles.
                                    </p>
                                )}

                                {/* Primary role selector � only shown when 2+ roles are active */}
                                {activeRoleCodes.length >= 2 && (
                                    <div className="flex items-center gap-2 flex-wrap pt-1 border-t border-gray-100">
                                        <span className="flex items-center gap-1 text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
                                            <Crown className="size-3" /> Primary
                                        </span>
                                        {activeRoleCodes.map(code => {
                                            const t = types.find(t => t.code === code);
                                            if (!t) return null;
                                            const isPrimary = primaryRole === code;
                                            return (
                                                <button
                                                    key={code}
                                                    type="button"
                                                    title={isPrimary ? 'Primary role' : 'Set as primary'}
                                                    disabled={isPrimary || roleLoading === code}
                                                    onClick={() => handleSetPrimary(code)}
                                                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                                                        isPrimary
                                                            ? 'bg-violet-600 text-white shadow-sm cursor-default'
                                                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200 cursor-pointer'
                                                    }`}
                                                >
                                                    {t.name}
                                                </button>
                                            );
                                        })}
                                        <span className="text-[10px] text-gray-300 ml-1">
                                            Determines default account group & transaction behaviour
                                        </span>
                                    </div>
                                )}
                            </div>
                        );
                    })()}

                    {/* ── Account Group � own row, directly after roles (cause → effect) ── */}
                    <div className="border-t border-gray-100 pt-4">
                        <div className="flex items-center justify-between mb-2">
                            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                Account Group <span className="text-red-400">*</span>
                            </p>
                            {groupAutoFilled && (
                                <span className="text-[10px] text-violet-500 font-medium flex items-center gap-1">
                                    <CheckCircle2 className="size-3" /> Auto-set from role � you can override
                                </span>
                            )}
                        </div>
                        <div className="grid grid-cols-2 gap-5">
                            <Controller name="ac_group" control={control} render={({ field }) => {
                                // Expose field.onChange to handleGroupPickerSelect (defined in LedgerForm scope)
                                groupFieldOnChange.current = field.onChange;
                                const selected = accounts.find(a => a.id.toString() === field.value);
                                return (
                                    <>
                                        <button
                                            ref={acGroupBtnRef}
                                            type="button"
                                            onClick={() => setPickerOpen(true)}
                                            className={`w-full h-11 flex items-center gap-2 px-3 rounded-md border text-sm text-left transition-colors focus:outline-none ${
                                                selected
                                                    ? 'border-violet-200 bg-violet-50 hover:border-violet-400'
                                                    : 'border-gray-200 bg-white hover:border-violet-400'
                                            }`}
                                        >
                                            {selected ? (
                                                <>
                                                    {selected.code && (
                                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-100 text-primary tracking-wider shrink-0">
                                                            {selected.code}
                                                        </span>
                                                    )}
                                                    <span className="text-gray-700 font-medium truncate">{selected.name}</span>
                                                </>
                                            ) : (
                                                <span className="text-gray-400">Select group�</span>
                                            )}
                                            <ChevronRight className="w-3.5 h-3.5 text-gray-300 ml-auto shrink-0" />
                                        </button>

                                        <Sheet open={pickerOpen} onOpenChange={(open) => {
                                            setPickerOpen(open);
                                            if (!open) setGroupSearch('');
                                        }}>
                                            <SheetContent
                                                side="right"
                                                className="w-[400px] sm:max-w-[400px] flex flex-col p-0"
                                                onCloseAutoFocus={(e) => {
                                                    e.preventDefault();
                                                    acGroupBtnRef.current?.focus();
                                                }}
                                            >
                                                <div className="flex items-center gap-3 px-6 py-4 bg-violet-50 border-b border-violet-100 shrink-0">
                                                    <span className="flex items-center justify-center size-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">≡</span>
                                                    <div>
                                                        <p className="text-sm font-bold text-primary tracking-widest uppercase">Select Account Group</p>
                                                        <p className="text-xs text-primary mt-0.5">Hover to see examples. Click to assign.</p>
                                                    </div>
                                                </div>
                                                {spellCheckEnabled && (
                                                    <div className="px-3 pt-3 pb-2 shrink-0 border-b border-violet-50">
                                                        <div className="relative">
                                                            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
                                                            <input
                                                                type="text"
                                                                value={groupSearch}
                                                                onChange={e => setGroupSearch(e.target.value)}
                                                                placeholder="Search groups�"
                                                                className="w-full h-9 pl-8 pr-3 text-sm rounded-md border border-gray-200 bg-white focus:outline-none focus:border-violet-400"
                                                                autoFocus
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                                <div className="flex-1 overflow-y-auto px-3 py-3">
                                                    {filteredAccounts !== null ? (
                                                        filteredAccounts.length === 0 ? (
                                                            <p className="text-xs text-gray-400 text-center py-8">No matching groups</p>
                                                        ) : (
                                                            filteredAccounts.map(acc => {
                                                                const _suggested = suggestGroupCode(acName);
                                                                const _isSugg = _suggested && acc.code === _suggested;
                                                                const _hint = GROUP_HINTS[acc.code];
                                                                const _isFa = FA_ASSET_CODES.has(acc.code);
                                                                return (
                                                                    <button
                                                                        key={acc.id}
                                                                        type="button"
                                                                        onClick={() => handleGroupPickerSelect(acc)}
                                                                        className={`w-full flex items-center gap-2 py-2 px-3 rounded-lg text-left transition-colors ${_isSugg ? 'bg-green-50 ring-1 ring-green-300 hover:bg-green-100' : 'hover:bg-violet-50'}`}
                                                                        title={_hint || undefined}
                                                                    >
                                                                        {acc.code && (
                                                                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 tracking-wider shrink-0">
                                                                                {acc.code}
                                                                            </span>
                                                                        )}
                                                                        <div className="flex flex-col min-w-0 flex-1">
                                                                            <div className="flex items-center gap-1.5">
                                                                                <span className="text-sm text-gray-700 truncate">{acc.name}</span>
                                                                                {_isSugg && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-green-200 text-green-800 shrink-0 uppercase tracking-wider">Suggested</span>}
                                                                                {_isFa && id && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 shrink-0 uppercase tracking-wider">Fixed Asset</span>}
                                                                            </div>
                                                                            {_hint && <span className="text-[10px] text-gray-400 truncate leading-tight mt-0.5">{_hint}</span>}
                                                                        </div>
                                                                    </button>
                                                                );
                                                            })
                                                        )
                                                    ) : (
                                                        accountTree.map(node => (
                                                            <GroupPickerNode
                                                                key={node.id}
                                                                node={node}
                                                                level={0}
                                                                onSelect={handleGroupPickerSelect}
                                                                suggestedCode={suggestGroupCode(acName)}
                                                                allowFa={!!id}
                                                            />
                                                        ))
                                                    )}
                                                </div>
                                            </SheetContent>
                                        </Sheet>
                                    </>
                                );
                            }} />
                        </div>
                    </div>

                    {/* ── CRM dates � separate, lower-priority row ── */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-5 pt-2">
                        <Field label="Birthday">
                            <Input className={inputCls} type="date" {...register("dob")} />
                        </Field>

                        <Field label="Anniversary">
                            <Input className={inputCls} type="date" {...register("anniversary")} />
                        </Field>
                    </div>

                </SectionCard>

                {/* ── Section 2: Contact & Address ─────────────────────────── */}
                <SectionCard number="2" title="Contact & Address">

                    {/* ── Billing Address ── */}
                    <div className="mb-1">
                        <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-3">
                            Billing Address
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                            <Field label="Address Line 1">
                                <Input className={inputCls}
                                    spellCheck={spellCheckEnabled}
                                    {...register("add1", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_add1", e.target.value);
                                        }
                                    })}
                                    placeholder="Street / Building" />
                            </Field>
                            <Field label="Address Line 2">
                                <Input className={inputCls}
                                    spellCheck={spellCheckEnabled}
                                    {...register("add2", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_add2", e.target.value);
                                        }
                                    })}
                                    placeholder="Area / Locality" />
                            </Field>
                            <Field label="City">
                                <Input className={inputCls}
                                    spellCheck={spellCheckEnabled}
                                    {...register("city", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_city", e.target.value);
                                        }
                                    })}
                                    placeholder="City" />
                            </Field>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-5 mt-5">
                            <Field label="Pincode">
                                <Input className={inputCls}
                                    {...register("pincode", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_pincode", e.target.value);
                                        }
                                    })}
                                    placeholder="6-digit pincode" maxLength={6} />
                            </Field>
                            <Field label="State">
                                <Controller name="state" control={control} render={({ field }) => (
                                    <Select
                                        onValueChange={(v) => {
                                            field.onChange(v);
                                            if (shippingSameAsBilling) setValue("ship_state", v);
                                        }}
                                        value={field.value}
                                    >
                                        <SelectTrigger className={triggerCls}><SelectValue placeholder="Select state" /></SelectTrigger>
                                        <SelectContent className="max-h-60 overflow-y-auto">
                                            <SelectItem value="none">� Select �</SelectItem>
                                            {states.map((s) => (
                                                <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )} />
                            </Field>
                        </div>
                    </div>

                    {/* ── Shipping Address ── */}
                    <div className="border-t border-gray-100 pt-5 mt-2">
                        <div className="flex items-center justify-between mb-3">
                            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                Shipping Address
                            </p>
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                                <Checkbox
                                    checked={shippingSameAsBilling}
                                    onCheckedChange={(checked) => {
                                        setShippingSameAsBilling(checked);
                                        if (checked) {
                                            // Mirror billing → shipping immediately
                                            setValue("ship_add1",    getValues("add1")    || '');
                                            setValue("ship_add2",    getValues("add2")    || '');
                                            setValue("ship_city",    getValues("city")    || '');
                                            setValue("ship_pincode", getValues("pincode") || '');
                                            setValue("ship_state",   getValues("state")   || 'none');
                                        }
                                    }}
                                />
                                <span className="text-xs text-gray-500">Same as billing address</span>
                            </label>
                        </div>

                        {shippingSameAsBilling ? (
                            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-3 flex items-center gap-2 text-xs text-gray-400">
                                <Copy className="w-3.5 h-3.5 shrink-0" />
                                Shipping address is the same as billing. Uncheck above to enter a different address.
                            </div>
                        ) : (
                            <>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                                    <Field label="Address Line 1">
                                        <Input className={inputCls} spellCheck={spellCheckEnabled} {...register("ship_add1")} placeholder="Street / Building" />
                                    </Field>
                                    <Field label="Address Line 2">
                                        <Input className={inputCls} spellCheck={spellCheckEnabled} {...register("ship_add2")} placeholder="Area / Locality" />
                                    </Field>
                                    <Field label="City">
                                        <Input className={inputCls} spellCheck={spellCheckEnabled} {...register("ship_city")} placeholder="City" />
                                    </Field>
                                </div>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-5 mt-5">
                                    <Field label="Pincode">
                                        <Input className={inputCls} {...register("ship_pincode")} placeholder="6-digit pincode" maxLength={6} />
                                    </Field>
                                    <Field label="State">
                                        <Controller name="ship_state" control={control} render={({ field }) => (
                                            <Select onValueChange={field.onChange} value={field.value || 'none'}>
                                                <SelectTrigger className={triggerCls}><SelectValue placeholder="Select state" /></SelectTrigger>
                                                <SelectContent className="max-h-60 overflow-y-auto">
                                                    <SelectItem value="none">� Select �</SelectItem>
                                                    {states.map((s) => (
                                                        <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        )} />
                                    </Field>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Divider between address and contact numbers */}
                    <div className="border-t border-gray-100 pt-2">
                        <p className="text-[11px] font-semibold text-gray-300 uppercase tracking-widest mb-4">
                            Phone &amp; Mobile
                        </p>
                        <div className="grid grid-cols-3 gap-5 mb-5">
                            <Field label="Phone 1">
                                <Input className={inputCls} type="tel" {...register("phone1")} placeholder="�" />
                            </Field>
                            <Field label="Phone 2">
                                <Input className={inputCls} type="tel" {...register("phone2")} placeholder="�" disabled={!watch("phone1")} />
                            </Field>
                            <Field label="Phone 3">
                                <Input className={inputCls} type="tel" {...register("phone3")} placeholder="�" disabled={!watch("phone2")} />
                            </Field>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                            <Field label="Mobile 1">
                                <Controller name="mobile1" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number" />
                                    )} />
                            </Field>
                            <Field label="Mobile 2">
                                <Controller name="mobile2" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number"
                                            disabled={!watch("mobile1")} />
                                    )} />
                            </Field>
                            <Field label="Mobile 3">
                                <Controller name="mobile3" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number"
                                            disabled={!watch("mobile2")} />
                                    )} />
                            </Field>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-5">
                        <Field label="Email">
                            <Input className={inputCls} type="email" {...register("email")} placeholder="email@example.com" />
                        </Field>
                        <Field label="Fax">
                            <Input className={inputCls} {...register("fax")} placeholder="Fax number" />
                        </Field>
                    </div>

                </SectionCard>

                {/* ── Section 3: Compliance & KYC ──────────────────────────── */}
                <SectionCard number="3" title="Compliance & KYC">

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                        <Field label="PAN" error={errors.pan?.message}>
                            <Input
                                className={`${inputCls} uppercase ${errors.pan ? 'border-red-400 focus:border-red-500' : ''}`}
                                {...register("pan", { validate: validatePAN })}
                                placeholder="ABCDE1234F"
                                maxLength={10}
                            />
                        </Field>
                        <Field label="GST Number" error={errors.gst?.message}>
                            <Input
                                className={`${inputCls} uppercase ${errors.gst ? 'border-red-400 focus:border-red-500' : ''}`}
                                {...register("gst", { validate: validateGST })}
                                placeholder="22AAAAA0000A1Z5"
                                maxLength={15}
                            />
                        </Field>
                        <Field label="Aadhar Number" error={errors.aadhar?.message}>
                            <Input className={`${inputCls} ${errors.aadhar ? 'border-red-400 focus:border-red-500' : ''}`} {...register("aadhar", { validate: validateAadhar })} placeholder="12-digit Aadhar" maxLength={12} />
                        </Field>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                        <Field label="Passport" error={errors.passport?.message}>
                            <Input className={`${inputCls} uppercase ${errors.passport ? 'border-red-400 focus:border-red-500' : ''}`} {...register("passport", { validate: validatePassport })} placeholder="Passport number" />
                        </Field>
                        <Field label="Driving License">
                            <Input className={`${inputCls} uppercase`} {...register("dl_no")} placeholder="DL number" />
                        </Field>
                        <Field label="Remarks">
                            <Input className={inputCls} spellCheck={spellCheckEnabled} {...register("remarks")} placeholder="Any additional notes�" />
                        </Field>
                    </div>

                    <div className="border-t border-gray-100 pt-4 mt-2">
                        <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-3">
                            KYC Documents
                        </p>
                        <LedgerDocuments
                            ledgerId={id}
                            ledgerName={watch("ac_name") || ""}
                            pendingDocs={pendingDocs}
                            onPendingChange={setPendingDocs}
                        />
                    </div>

                </SectionCard>

                {/* ── Section 4: TDS Configuration ─────────────────────────── */}
                {primaryRole && !['CA','BA','CO','INC'].includes(primaryRole) && (
                    <SectionCard number="4" title="TDS Configuration">
                        <div className="flex items-center gap-3 mb-2">
                            <Controller name="tds_applicable" control={control} render={({ field }) => (
                                <Checkbox
                                    id="tds_applicable"
                                    checked={!!field.value}
                                    onCheckedChange={field.onChange}
                                />
                            )} />
                            <label htmlFor="tds_applicable" className="text-sm text-gray-700 cursor-pointer select-none">
                                TDS Applicable for this party
                            </label>
                        </div>

                        {watch('tds_applicable') && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">
                                <Field label="TDS Section">
                                    <Controller name="tds_section" control={control} render={({ field }) => (
                                        <Select onValueChange={field.onChange} value={field.value}>
                                            <SelectTrigger className={triggerCls}><SelectValue placeholder="Select section�" /></SelectTrigger>
                                            <SelectContent>
                                                {tdsSections.map(s => (
                                                    <SelectItem key={s.id} value={String(s.id)}>
                                                        {s.section_code} � {s.description}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    )} />
                                </Field>

                                <Field label="Deductor Type">
                                    <Controller name="tds_deductor_type" control={control} render={({ field }) => (
                                        <Select onValueChange={field.onChange} value={field.value}>
                                            <SelectTrigger className={triggerCls}><SelectValue placeholder="Select�" /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="IND">Individual / HUF</SelectItem>
                                                <SelectItem value="CO">Company / Firm</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    )} />
                                </Field>
                            </div>
                        )}

                        {watch('tds_applicable') && !watch('pan') && (
                            <p className="text-xs text-amber-600 mt-2">
                                ⚠ No PAN on file � higher TDS rate (20%) will apply. Add PAN in Compliance & KYC section.
                            </p>
                        )}
                    </SectionCard>
                )}

                {/* ── Footer ───────────────────────────────────────────────── */}
                <div className="flex justify-end items-center gap-3 pt-2">
                    <Button type="button" variant="outline" onClick={() => navigate('/crm/ledger')} className="h-10 px-5">
                        Cancel
                    </Button>
                    <Button type="submit" disabled={!!id && !isDirty} className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm">
                        {id ? 'Update Ledger' : 'Save Ledger'}
                    </Button>
                </div>

            </form>

            {/* ── FA Details Modal (Expense → FA reclassification) ──────────── */}
            <Dialog open={faModalOpen} onOpenChange={(open) => {
                if (!open) {
                    // User dismissed modal � reset pending group so picker reverts
                    setPendingFaGroup(null);
                }
                setFaModalOpen(open);
            }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="text-base font-bold text-gray-900">
                            Register as Fixed Asset
                        </DialogTitle>
                        <p className="text-sm text-gray-500 mt-1">
                            Moving this ledger to <span className="font-semibold text-primary">{pendingFaGroup?.name}</span> requires Fixed Asset details. A Fixed Asset record will be created automatically.
                        </p>
                    </DialogHeader>

                    <div className="space-y-4 py-2">
                        {/* Row 1: Purchase Date + Purchase Cost */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    Purchase Date <span className="text-red-400">*</span>
                                </label>
                                <Input
                                    type="date"
                                    value={faDetails.purchase_date}
                                    onChange={e => setFaDetails(d => ({ ...d, purchase_date: e.target.value }))}
                                    className="h-10 text-sm border-gray-200 focus:border-violet-400"
                                />
                            </div>
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    Purchase Cost (₹) <span className="text-red-400">*</span>
                                </label>
                                <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    placeholder="0.00"
                                    value={faDetails.purchase_cost}
                                    onChange={e => setFaDetails(d => ({ ...d, purchase_cost: e.target.value }))}
                                    className="h-10 text-sm border-gray-200 focus:border-violet-400"
                                />
                            </div>
                        </div>

                        {/* Row 2: Residual Value + IT Block */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    Residual Value (₹)
                                </label>
                                <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    placeholder="0"
                                    value={faDetails.residual_value}
                                    onChange={e => setFaDetails(d => ({ ...d, residual_value: e.target.value }))}
                                    className="h-10 text-sm border-gray-200 focus:border-violet-400"
                                />
                            </div>
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    IT Block Category <span className="text-red-400">*</span>
                                </label>
                                <Select
                                    value={faDetails.it_block_category}
                                    onValueChange={v => {
                                        const defaultRate = IT_BLOCK_DEFAULT_RATE[v] ?? '';
                                        setFaDetails(d => ({ ...d, it_block_category: v, rate_or_life: String(defaultRate) }));
                                    }}
                                >
                                    <SelectTrigger className="h-10 text-sm border-gray-200 focus:border-violet-400">
                                        <SelectValue placeholder="Select category�" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(FA_GROUP_IT_BLOCKS[pendingFaGroup?.code] ?? []).map(opt => (
                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Row 3: Depreciation Method + Rate / Life */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    Depreciation Method <span className="text-red-400">*</span>
                                </label>
                                <div className="flex rounded-md border border-gray-200 overflow-hidden h-10">
                                    {['WDV', 'SLM'].map(m => (
                                        <button
                                            key={m}
                                            type="button"
                                            onClick={() => setFaDetails(d => ({ ...d, depreciation_method: m }))}
                                            className={`flex-1 text-sm font-medium transition-colors ${
                                                faDetails.depreciation_method === m
                                                    ? 'bg-primary text-white'
                                                    : 'bg-white text-gray-600 hover:bg-gray-50'
                                            }`}
                                        >
                                            {m}
                                        </button>
                                    ))}
                                </div>
                                <p className="text-[10px] text-gray-400">
                                    {faDetails.depreciation_method === 'WDV' ? 'Written Down Value � rate applied on book value' : 'Straight Line Method � equal charge each year'}
                                </p>
                            </div>
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                    {faDetails.depreciation_method === 'WDV' ? 'Rate (%)' : 'Useful Life (years)'} <span className="text-red-400">*</span>
                                </label>
                                <Input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    placeholder={faDetails.depreciation_method === 'WDV' ? 'e.g. 15' : 'e.g. 5'}
                                    value={faDetails.rate_or_life}
                                    onChange={e => setFaDetails(d => ({ ...d, rate_or_life: e.target.value }))}
                                    className="h-10 text-sm border-gray-200 focus:border-violet-400"
                                />
                            </div>
                        </div>

                        {/* Row 4: Description */}
                        <div className="flex flex-col gap-1.5">
                            <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                Description
                            </label>
                            <textarea
                                rows={2}
                                placeholder="Optional notes about this asset�"
                                value={faDetails.description}
                                onChange={e => setFaDetails(d => ({ ...d, description: e.target.value }))}
                                className="w-full px-3 py-2 text-sm rounded-md border border-gray-200 focus:outline-none focus:border-violet-400 resize-none"
                            />
                        </div>
                    </div>

                    <DialogFooter className="gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                                setPendingFaGroup(null);
                                setFaModalOpen(false);
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            onClick={() => {
                                // Validate required fields
                                const missing = [];
                                if (!faDetails.purchase_date) missing.push('Purchase Date');
                                if (!faDetails.purchase_cost || Number(faDetails.purchase_cost) <= 0) missing.push('Purchase Cost');
                                if (!faDetails.it_block_category) missing.push('IT Block Category');
                                if (!faDetails.rate_or_life || Number(faDetails.rate_or_life) <= 0) missing.push(faDetails.depreciation_method === 'WDV' ? 'Rate (%)' : 'Useful Life');
                                if (missing.length > 0) {
                                    toast({ title: "Required fields missing", description: missing.join(', '), variant: "destructive" });
                                    return;
                                }
                                // Confirm: update group selection and mark fa_data as confirmed
                                groupFieldOnChange.current?.(pendingFaGroup.id.toString());
                                setGroupAutoFilled(false);
                                setFaDetailsConfirmed(true);
                                setFaModalOpen(false);
                            }}
                            className="bg-primary text-white hover:bg-primary/90"
                        >
                            Confirm & Assign Group
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ── FA Remove Confirmation Dialog (FA → Expense reclassification) ── */}
            <Dialog open={faRemoveConfirmOpen} onOpenChange={(open) => {
                if (!open) setPendingNonFaGroup(null);
                setFaRemoveConfirmOpen(open);
            }}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-base font-bold text-gray-900">
                            Remove Fixed Asset record?
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3 py-1 text-sm text-gray-600">
                        <p>
                            This ledger is linked to a <span className="font-semibold">Fixed Asset</span>. Moving it to{' '}
                            <span className="font-semibold text-primary">{pendingNonFaGroup?.name}</span> will permanently delete the Fixed Asset record.
                        </p>
                        <p className="text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 text-xs">
                            This is only possible if <strong>no depreciation</strong> has been posted against this asset. If depreciation exists, you must dispose the asset through Fixed Assets → Asset Master first.
                        </p>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                                setPendingNonFaGroup(null);
                                setFaRemoveConfirmOpen(false);
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            variant="destructive"
                            onClick={() => {
                                groupFieldOnChange.current?.(pendingNonFaGroup.id.toString());
                                setGroupAutoFilled(false);
                                setFaRemoveConfirmOpen(false);
                            }}
                        >
                            Confirm Reclassification
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    );
};

export default LedgerForm;
